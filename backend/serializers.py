"""JSON serialization helpers shared by the REST endpoints and WebSockets.

Keeping these in one place is what lets `event_update` / `roster_update` chat
frames stay byte-for-byte in sync with the matching REST payloads.
"""

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from config import SYSTEM_SENDER_ADDRESS, is_admin_address
from models import Message, Room, RoomEvent, RoomEventRsvp, User


def _iso(dt: datetime) -> str:
    """Serialize a datetime to ISO 8601, appending `Z` for naive UTC values."""
    return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()


def _user_payload(user: User) -> dict:
    """Public-facing serialization of a user (shared by GET/PATCH /users/me)."""
    return {
        "id": user.id,
        "identity_address": user.identity_address,
        "username": user.username,
        "created_at": _iso(user.created_at),
        "last_login": _iso(user.last_login) if user.last_login else None,
        "is_admin": is_admin_address(user.identity_address),
    }


def _members_payload(room: Room) -> list[dict[str, str | bool]]:
    """Compact roster for chat WS `roster_update` frames."""
    return [
        {
            "address": m.identity_address,
            "username": m.username,
            "is_admin": is_admin_address(m.identity_address),
        }
        for m in room.members
    ]


def _serialize_event_state(session: Session, room: Room) -> dict | None:
    """Build the JSON payload for a room's scheduled event.

    Returns `None` when the room has no event yet. Used by both the REST
    endpoints and the chat WebSocket so that `event_update` frames stay
    in sync with `GET /rooms/{name}/event`.
    """
    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        return None

    rsvp_rows = session.exec(
        select(RoomEventRsvp, User)
        .join(User, User.id == RoomEventRsvp.user_id)
        .where(RoomEventRsvp.event_id == event.id)
    ).all()

    return {
        "starts_at": _iso(event.starts_at),
        "ends_at": _iso(event.ends_at),
        "created_by": event.created_by,
        "created_at": _iso(event.created_at),
        "updated_at": _iso(event.updated_at),
        "rsvps": [
            {
                "address": user.identity_address,
                "username": user.username,
                "status": rsvp.status.value,
                "updated_at": _iso(rsvp.updated_at),
            }
            for rsvp, user in rsvp_rows
        ],
    }


def _msg_dict(msg: Message, sender_username: str) -> dict:
    payload = {
        "id": msg.id,
        "sender_address": msg.sender_address,
        "sender_username": sender_username,
        "content": msg.content,
        "created_at": _iso(msg.created_at),
        "signature": msg.signature,
        "sent_at": msg.sent_at,
        "verified": msg.signature is not None,
    }
    if msg.sender_address == SYSTEM_SENDER_ADDRESS:
        payload["kind"] = "system"
    return payload


def get_rooms_payload(session: Session) -> str:
    now = datetime.now(UTC)

    # Optional cleanup of expired rooms before returning the payload.
    # NOTE: The DB layer also has ON DELETE CASCADE on RoomEvent / RoomEventRsvp
    # / Message, but we delete explicitly so the same code path works on
    # SQLite (test environment) where FK cascades depend on PRAGMA settings.
    expired_rooms = session.exec(select(Room).where(Room.expires_at <= now)).all()
    for er in expired_rooms:
        old_messages = session.exec(
            select(Message).where(Message.room_id == er.id)
        ).all()
        for m in old_messages:
            session.delete(m)
        old_event = session.exec(
            select(RoomEvent).where(RoomEvent.room_id == er.id)
        ).first()
        if old_event is not None:
            old_rsvps = session.exec(
                select(RoomEventRsvp).where(RoomEventRsvp.event_id == old_event.id)
            ).all()
            for r in old_rsvps:
                session.delete(r)
            session.delete(old_event)
        session.delete(er)
    if expired_rooms:
        session.commit()

    return json.dumps(
        [
            {
                "name": r.name,
                "game": r.game,
                "lobby_location": r.lobby_location,
                "players_active": len(r.members),
                "players_max": r.players_max,
                "member_addresses": [m.identity_address for m in r.members],
                "description": r.description,
                "communicator_link": r.communicator_link,
                "requirements": r.requirements,
                "expires_at": _iso(r.expires_at),
            }
            for r in session.exec(select(Room)).all()
        ]
    )
