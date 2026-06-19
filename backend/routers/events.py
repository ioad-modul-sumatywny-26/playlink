"""Scheduled room event endpoints and RSVPs."""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from config import DEFAULT_RATE_LIMIT
from dependencies import SessionDep, get_current_user_address
from models import Room, RoomEvent, RoomEventRsvp, User
from rate_limit import limiter
from schemas import ScheduleEventRequest, SetRsvpRequest
from serializers import _iso, _serialize_event_state, get_rooms_payload
from ws.managers import chat_manager, manager

router = APIRouter(tags=["events"])


@router.get("/rooms/{room_name}/event")
@limiter.limit(DEFAULT_RATE_LIMIT)
def get_room_event(request: Request, room_name: str, session: SessionDep):  # noqa: ARG001
    """Return the room's scheduled event (if any), including the RSVP roster.

    Mirrors `GET /rooms/{name}` in being public — anyone can browse the
    schedule, only members are allowed to RSVP.
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    event_state = _serialize_event_state(session, room)
    if event_state is None:
        raise HTTPException(status_code=404, detail="No event scheduled")
    return event_state


@router.put("/rooms/{room_name}/event", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def schedule_room_event(
    request: Request,  # noqa: ARG001
    room_name: str,
    body: ScheduleEventRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Create or replace the scheduled event for a room.

    Only the room creator may schedule. `starts_at` must lie in the future
    and `ends_at` must come after `starts_at`. The room's `expires_at` is
    automatically extended past `ends_at` so the room stays alive until the
    event finishes (plus a small grace period for stragglers).
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.created_by.lower() != address.lower():
        raise HTTPException(
            status_code=403, detail="Only the room creator can schedule an event"
        )

    starts_at = body.starts_at
    ends_at = body.ends_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    else:
        starts_at = starts_at.astimezone(UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)
    else:
        ends_at = ends_at.astimezone(UTC)

    now = datetime.now(UTC)
    if starts_at <= now:
        raise HTTPException(status_code=400, detail="starts_at must be in the future")
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="ends_at must be after starts_at")

    # Keep the room alive for the entire event plus a 30-minute grace period
    # so members don't get prune'd out mid-session.
    grace = timedelta(minutes=30)
    expires_at = room.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    new_expiry = max(expires_at, ends_at + grace)
    room_expiry_changed = new_expiry != expires_at
    if room_expiry_changed:
        room.expires_at = new_expiry
        session.add(room)

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        event = RoomEvent(
            room_id=room.id,
            starts_at=starts_at,
            ends_at=ends_at,
            created_by=address,
        )
        session.add(event)
    else:
        # If the time window shifted at all, every RSVP was a decision about
        # the old time — drop them so members re-confirm against the new slot.
        existing_starts = event.starts_at
        existing_ends = event.ends_at
        if existing_starts.tzinfo is None:
            existing_starts = existing_starts.replace(tzinfo=UTC)
        if existing_ends.tzinfo is None:
            existing_ends = existing_ends.replace(tzinfo=UTC)
        time_changed = existing_starts != starts_at or existing_ends != ends_at
        if time_changed:
            stale_rsvps = session.exec(
                select(RoomEventRsvp).where(RoomEventRsvp.event_id == event.id)
            ).all()
            for rsvp in stale_rsvps:
                session.delete(rsvp)
        event.starts_at = starts_at
        event.ends_at = ends_at
        event.updated_at = datetime.now(UTC)
        session.add(event)
    session.commit()

    payload = _serialize_event_state(session, room)
    await chat_manager.broadcast(
        room_name, json.dumps({"type": "event_update", "event": payload})
    )
    if room_expiry_changed:
        await manager.broadcast(get_rooms_payload(session))
    return payload


@router.delete("/rooms/{room_name}/event", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def cancel_room_event(
    request: Request,  # noqa: ARG001
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Delete the scheduled event for a room and clear all RSVPs."""
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.created_by.lower() != address.lower():
        raise HTTPException(
            status_code=403, detail="Only the room creator can cancel the event"
        )

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        raise HTTPException(status_code=404, detail="No event scheduled")

    rsvps = session.exec(
        select(RoomEventRsvp).where(RoomEventRsvp.event_id == event.id)
    ).all()
    for r in rsvps:
        session.delete(r)
    session.delete(event)
    session.commit()

    await chat_manager.broadcast(
        room_name, json.dumps({"type": "event_update", "event": None})
    )
    return {"status": "cancelled", "room": room.name}


@router.put("/rooms/{room_name}/event/rsvp", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def set_room_event_rsvp(
    request: Request,  # noqa: ARG001
    room_name: str,
    body: SetRsvpRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Upsert the caller's RSVP for the room's scheduled event.

    Only current members of the room may RSVP. The caller's status
    overwrites any previous one (one RSVP per user per event).
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in room.members:
        raise HTTPException(
            status_code=403, detail="Only room members can RSVP to the event"
        )

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        raise HTTPException(status_code=404, detail="No event scheduled")

    rsvp = session.exec(
        select(RoomEventRsvp).where(
            RoomEventRsvp.event_id == event.id,
            RoomEventRsvp.user_id == user.id,
        )
    ).first()
    if rsvp is None:
        rsvp = RoomEventRsvp(
            event_id=event.id,
            user_id=user.id,
            status=body.status,
        )
        session.add(rsvp)
    else:
        rsvp.status = body.status
        rsvp.updated_at = datetime.now(UTC)
        session.add(rsvp)
    session.commit()
    session.refresh(rsvp)

    rsvp_payload = {
        "address": user.identity_address,
        "username": user.username,
        "status": rsvp.status.value,
        "updated_at": _iso(rsvp.updated_at),
    }
    await chat_manager.broadcast(
        room_name, json.dumps({"type": "rsvp_update", "rsvp": rsvp_payload})
    )
    return rsvp_payload
