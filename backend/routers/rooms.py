"""Room lifecycle and membership endpoints."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlmodel import select

from config import (
    DEFAULT_RATE_LIMIT,
    LOBBY_LOCATION_CODES,
    LOBBY_LOCATIONS,
    SYSTEM_SENDER_ADDRESS,
    is_admin_address,
)
from dependencies import (
    SessionDep,
    get_admin_address,
    get_current_user_address,
)
from models import (
    DEFAULT_LOBBY_LOCATION,
    Message,
    Room,
    RoomEvent,
    RoomEventRsvp,
    User,
)
from rate_limit import limiter
from schemas import CreateRoomRequest
from serializers import (
    _iso,
    _members_payload,
    _msg_dict,
    _serialize_event_state,
    get_rooms_payload,
)
from services import _ensure_game, _purge_room
from ws.managers import chat_manager, manager

router = APIRouter(tags=["rooms"])


@router.get("/rooms")
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_rooms(request: Request, session: SessionDep):  # noqa: ARG001
    return session.exec(select(Room)).all()


@router.get("/lobby-locations")
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_lobby_locations(request: Request):  # noqa: ARG001
    return {"default": DEFAULT_LOBBY_LOCATION, "locations": LOBBY_LOCATIONS}


@router.get("/rooms/{room_name}")
@limiter.limit(DEFAULT_RATE_LIMIT)
def get_room(request: Request, room_name: str, session: SessionDep):  # noqa: ARG001
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "name": room.name,
        "game": room.game,
        "lobby_location": room.lobby_location,
        "players_max": room.players_max,
        "players_active": len(room.members),
        "member_addresses": [m.identity_address for m in room.members],
        "members": _members_payload(room),
        "description": room.description,
        "communicator_link": room.communicator_link,
        "requirements": room.requirements,
        "created_by": room.created_by,
        "expires_at": _iso(room.expires_at),
        "event": _serialize_event_state(session, room),
    }


@router.delete(
    "/rooms/{room_name}",
    status_code=200,
    dependencies=[Depends(get_admin_address)],
)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def delete_room(
    request: Request,  # noqa: ARG001
    room_name: str,
    session: SessionDep,
):
    """Admin-only: close a room.

    Cascades deletion of the room's chat messages, scheduled event and RSVPs,
    notifies anyone connected to the room's chat via a `room_closed` frame so
    their client can redirect them out, and broadcasts the refreshed active
    rooms list to all global listeners.
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    _purge_room(session, room)
    session.commit()

    await chat_manager.broadcast(
        room_name, json.dumps({"type": "room_closed", "room": room_name})
    )
    await manager.broadcast(get_rooms_payload(session))
    return {"status": "closed", "room": room_name}


@router.post("/rooms", status_code=201)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def create_room(
    request: Request,  # noqa: ARG001
    body: CreateRoomRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    now = datetime.now(UTC)

    # Clean up expired rooms for accurate counts
    expired_rooms = session.exec(select(Room).where(Room.expires_at <= now)).all()
    for er in expired_rooms:
        old_messages = session.exec(
            select(Message).where(Message.room_id == er.id)
        ).all()
        for m in old_messages:
            session.delete(m)
        session.delete(er)
    session.commit()

    existing = session.exec(select(Room).where(Room.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Room name already taken")

    if not is_admin_address(address):
        user_rooms_count = len(
            session.exec(select(Room).where(Room.created_by == address)).all()
        )
        if user_rooms_count >= 3:
            raise HTTPException(
                status_code=400, detail="You can create a maximum of 3 rooms."
            )

    game_name = body.game.strip()
    if not game_name:
        raise HTTPException(status_code=400, detail="Game name is required")

    lobby_location = body.lobby_location.strip()
    if lobby_location not in LOBBY_LOCATION_CODES:
        raise HTTPException(status_code=400, detail="Unsupported lobby location")

    _ = _ensure_game(session, game_name)

    room = Room(
        name=body.name,
        game=game_name,
        lobby_location=lobby_location,
        players_max=body.players_max,
        description=body.description,
        communicator_link=(
            str(body.communicator_link) if body.communicator_link else None
        ),
        requirements=body.requirements,
        created_by=address,
    )

    # Auto-join creator
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if user:
        room.members.append(user)

    session.add(room)
    session.commit()
    session.refresh(room)

    await manager.broadcast(get_rooms_payload(session))
    return {"status": "created", "room": room.name}


@router.post("/rooms/{room_name}/join", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def join_room(
    request: Request,  # noqa: ARG001
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user in room.members:
        raise HTTPException(status_code=400, detail="You are already in this room")

    if len(room.members) >= room.players_max:
        raise HTTPException(status_code=400, detail="Room is full")

    room.members.append(user)
    session.add(room)
    session.commit()

    await manager.broadcast(get_rooms_payload(session))
    await chat_manager.broadcast(
        room_name,
        json.dumps({"type": "roster_update", "members": _members_payload(room)}),
    )
    return {"status": "joined", "room": room.name}


@router.post("/rooms/{room_name}/leave", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def leave_room(
    request: Request,  # noqa: ARG001
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in room.members:
        raise HTTPException(status_code=400, detail="You are not in this room")

    # Drop the leaving user's RSVP (if any) so an event's roster reflects
    # the current member set. Idempotent — runs even when no event exists.
    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    rsvp_to_drop: RoomEventRsvp | None = None
    if event is not None:
        rsvp_to_drop = session.exec(
            select(RoomEventRsvp).where(
                RoomEventRsvp.event_id == event.id,
                RoomEventRsvp.user_id == user.id,
            )
        ).first()
        if rsvp_to_drop is not None:
            session.delete(rsvp_to_drop)

    room.members.remove(user)
    session.add(room)
    session.commit()

    await manager.broadcast(get_rooms_payload(session))
    await chat_manager.broadcast(
        room_name,
        json.dumps({"type": "roster_update", "members": _members_payload(room)}),
    )
    if rsvp_to_drop is not None:
        await chat_manager.broadcast(
            room_name,
            json.dumps(
                {"type": "event_update", "event": _serialize_event_state(session, room)}
            ),
        )
    return {"status": "left", "room": room.name}


@router.post("/rooms/{room_name}/members/{member_address}/kick", status_code=200)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def kick_room_member(
    request: Request,  # noqa: ARG001
    room_name: str,
    member_address: str,
    session: SessionDep,
    admin_address: Annotated[str, Depends(get_admin_address)],
):
    """Remove a non-admin member and disconnect their active chat sessions."""
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    target = session.exec(
        select(User).where(func.lower(User.identity_address) == member_address.lower())
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if is_admin_address(target.identity_address):
        raise HTTPException(status_code=403, detail="Administrators cannot be kicked")
    if target not in room.members:
        raise HTTPException(status_code=409, detail="User is not a room member")

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is not None:
        rsvp = session.exec(
            select(RoomEventRsvp).where(
                RoomEventRsvp.event_id == event.id,
                RoomEventRsvp.user_id == target.id,
            )
        ).first()
        if rsvp is not None:
            session.delete(rsvp)

    ownership_transferred = room.created_by.lower() == target.identity_address.lower()
    if ownership_transferred:
        room.created_by = admin_address

    room.members.remove(target)
    system_message = Message(
        room_id=room.id,
        sender_address=SYSTEM_SENDER_ADDRESS,
        content=(f"{target.username} was removed from the room by an administrator."),
    )
    session.add(room)
    session.add(system_message)
    session.commit()
    session.refresh(system_message)

    await chat_manager.broadcast(
        room_name,
        json.dumps(
            {
                "type": "message",
                "message": _msg_dict(system_message, "System"),
            }
        ),
    )
    await chat_manager.broadcast(
        room_name,
        json.dumps({"type": "roster_update", "members": _members_payload(room)}),
    )
    if event is not None:
        await chat_manager.broadcast(
            room_name,
            json.dumps(
                {"type": "event_update", "event": _serialize_event_state(session, room)}
            ),
        )
    await chat_manager.broadcast(
        room_name,
        json.dumps(
            {
                "type": "member_kicked",
                "member_address": target.identity_address,
                "member_username": target.username,
                "created_by": room.created_by,
                "ownership_transferred": ownership_transferred,
            }
        ),
    )
    await manager.broadcast(get_rooms_payload(session))
    await chat_manager.disconnect_user(room_name, target.identity_address)

    return {
        "status": "kicked",
        "member_address": target.identity_address,
        "member_username": target.username,
        "created_by": room.created_by,
        "ownership_transferred": ownership_transferred,
    }
