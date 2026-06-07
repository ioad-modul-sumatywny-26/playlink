"""Tests for the room cleanup functionality."""

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Message, Room, User


def _auth_headers() -> tuple[dict[str, str], str]:
    """Helper to create auth headers for tests."""
    import os

    import jwt
    from eth_account import Account

    acct = Account.create()
    address = acct.address
    secret = os.environ["JWT_SECRET"]
    payload = {
        "sub": address,
        "username": "tester",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}, address


def test_cleanup_removes_expired_rooms(client: TestClient, session: Session):
    """Verify that get_rooms_payload cleans up expired rooms and messages."""
    headers, address = _auth_headers()
    user = User(identity_address=address)
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create an already-expired room
    now = datetime.now(UTC)
    expired_room = Room(
        name="expired-cleanup-test",
        game="Quake III Arena",
        lobby_location="eu-central",
        players_max=4,
        created_by=address,
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(seconds=1),
    )
    expired_room.members.append(user)
    session.add(expired_room)
    session.commit()
    room_id = expired_room.id

    # Add a message to the expired room
    msg = Message(
        room_id=room_id,
        sender_address=address,
        content="old message",
    )
    session.add(msg)
    session.commit()

    # Verify they exist in DB before cleanup
    assert session.exec(select(Room).where(Room.id == room_id)).first() is not None
    assert (
        len(session.exec(select(Message).where(Message.room_id == room_id)).all()) == 1
    )

    # Call get_rooms_payload which triggers cleanup
    from main import get_rooms_payload

    payload_json = get_rooms_payload(session)
    rooms_list = json.loads(payload_json)

    # Verify the expired room is not in the payload
    assert not any(r["name"] == "expired-cleanup-test" for r in rooms_list)

    # Verify the expired room and message were deleted from DB
    assert session.exec(select(Room).where(Room.id == room_id)).first() is None
    assert (
        len(session.exec(select(Message).where(Message.room_id == room_id)).all()) == 0
    )


def test_cleanup_does_not_remove_valid_rooms(client: TestClient, session: Session):
    """Verify that cleanup only removes expired rooms, not valid ones."""
    headers, address = _auth_headers()
    user = User(identity_address=address)
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create a valid (not-expired) room
    now = datetime.now(UTC)
    valid_room = Room(
        name="valid-room-test",
        game="Diablo II",
        lobby_location="eu-central",
        players_max=4,
        created_by=address,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    valid_room.members.append(user)
    session.add(valid_room)
    session.commit()
    room_id = valid_room.id

    # Call get_rooms_payload
    from main import get_rooms_payload

    payload_json = get_rooms_payload(session)
    rooms_list = json.loads(payload_json)

    # Verify the valid room still exists
    assert any(r["name"] == "valid-room-test" for r in rooms_list)
    assert session.exec(select(Room).where(Room.id == room_id)).first() is not None
