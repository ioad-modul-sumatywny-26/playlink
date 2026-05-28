import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import main
from models import Message, Room, RoomEvent, RoomEventRsvp, RoomMember, User


def _mint_token(address: str, *, is_admin: bool = False) -> str:
    secret = os.environ["JWT_SECRET"]
    payload = {
        "sub": address,
        "username": "tester",
        "is_admin": is_admin,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def admin_headers():
    """Whitelist a fresh admin address and yield its auth headers.

    The address is registered in `main.ADMIN_ADDRESSES` for the duration of the
    test and removed afterwards so tests don't leak admin grants into each other.
    """
    address = Account.create().address
    main.ADMIN_ADDRESSES.add(address.lower())
    try:
        yield (
            {"Authorization": f"Bearer {_mint_token(address, is_admin=True)}"},
            address,
        )
    finally:
        main.ADMIN_ADDRESSES.discard(address.lower())


def _regular_headers() -> tuple[dict[str, str], str]:
    address = Account.create().address
    return {"Authorization": f"Bearer {_mint_token(address)}"}, address


def _create_user(session: Session, address: str) -> User:
    user = User(identity_address=address)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #


def test_delete_room_requires_auth(client: TestClient):
    res = client.delete("/rooms/whatever")
    assert res.status_code == 401


def test_delete_room_forbidden_for_regular_user(client: TestClient):
    headers, _ = _regular_headers()
    res = client.delete("/rooms/whatever", headers=headers)
    assert res.status_code == 403


def test_create_game_forbidden_for_regular_user(client: TestClient):
    headers, _ = _regular_headers()
    res = client.post("/games", json={"name": "Doom"}, headers=headers)
    assert res.status_code == 403


def test_delete_game_forbidden_for_regular_user(client: TestClient):
    headers, _ = _regular_headers()
    res = client.delete("/games/Diablo II", headers=headers)
    assert res.status_code == 403


# --------------------------------------------------------------------------- #
# is_admin flag
# --------------------------------------------------------------------------- #


def test_users_me_reports_admin(client: TestClient, session: Session, admin_headers):
    headers, address = admin_headers
    _create_user(session, address)
    res = client.get("/users/me", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["is_admin"] is True
    assert body["identity_address"] == address


def test_users_me_reports_non_admin(client: TestClient, session: Session):
    headers, address = _regular_headers()
    _create_user(session, address)
    res = client.get("/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_admin"] is False


# --------------------------------------------------------------------------- #
# Delete room (admin)
# --------------------------------------------------------------------------- #


def test_admin_delete_room_missing(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.delete("/rooms/nope", headers=headers)
    assert res.status_code == 404


def test_admin_delete_room_cascades(
    client: TestClient, session: Session, admin_headers
):
    headers, _ = admin_headers
    member = _create_user(session, "0xMember")

    room = Room(
        name="doomed", game="Quake III Arena", players_max=4, created_by="0xMember"
    )
    room.members.append(member)
    session.add(room)
    session.commit()
    session.refresh(room)

    event = RoomEvent(
        room_id=room.id,
        starts_at=datetime.now(UTC) + timedelta(hours=1),
        ends_at=datetime.now(UTC) + timedelta(hours=2),
        created_by="0xMember",
    )
    session.add(event)
    session.add(Message(room_id=room.id, sender_address="0xMember", content="hi"))
    session.commit()
    session.refresh(event)
    session.add(RoomEventRsvp(event_id=event.id, user_id=member.id, status="present"))
    session.commit()

    res = client.delete("/rooms/doomed", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "closed"

    assert session.exec(select(Room).where(Room.name == "doomed")).first() is None
    assert session.exec(select(Message)).all() == []
    assert session.exec(select(RoomEvent)).all() == []
    assert session.exec(select(RoomEventRsvp)).all() == []
    assert session.exec(select(RoomMember)).all() == []
    # The user themselves must survive — only the room and its links go away.
    assert session.exec(select(User).where(User.id == member.id)).first() is not None


def test_admin_delete_room_broadcasts_room_closed(
    client: TestClient, session: Session, admin_headers
):
    headers, _ = admin_headers
    member_addr = "0xWatcher"
    _create_user(session, member_addr)
    room = Room(name="live", game="Diablo II", players_max=4, created_by=member_addr)
    member = session.exec(
        select(User).where(User.identity_address == member_addr)
    ).first()
    room.members.append(member)
    session.add(room)
    session.commit()

    token = _mint_token(member_addr)
    with client.websocket_connect(f"/ws/rooms/live/chat?token={token}") as ws:
        assert ws.receive_json()["type"] == "history"
        res = client.delete("/rooms/live", headers=headers)
        assert res.status_code == 200
        frame = ws.receive_json()
        assert frame == {"type": "room_closed", "room": "live"}


# --------------------------------------------------------------------------- #
# Create game (admin)
# --------------------------------------------------------------------------- #


def test_admin_create_game(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.post("/games", json={"name": "DOOM"}, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "DOOM"
    # Five seeded games already exist (sort_order 1..5) → new one is 6.
    assert body["sort_order"] == 6
    assert "DOOM" in client.get("/games").json()


def test_admin_create_game_duplicate(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.post("/games", json={"name": "Diablo II"}, headers=headers)
    assert res.status_code == 409


def test_admin_create_game_blank_rejected(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.post("/games", json={"name": "   "}, headers=headers)
    assert res.status_code == 400


# --------------------------------------------------------------------------- #
# Delete game (admin)
# --------------------------------------------------------------------------- #


def test_admin_delete_game_no_rooms(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.delete("/games/Half-Life", headers=headers)
    assert res.status_code == 200
    assert "Half-Life" not in client.get("/games").json()


def test_admin_delete_game_missing(client: TestClient, admin_headers):
    headers, _ = admin_headers
    res = client.delete("/games/Nonexistent", headers=headers)
    assert res.status_code == 404


def test_admin_delete_game_blocked_by_active_rooms(
    client: TestClient, session: Session, admin_headers
):
    headers, _ = admin_headers
    session.add(
        Room(name="q3-1", game="Quake III Arena", players_max=4, created_by="0x1")
    )
    session.add(
        Room(name="q3-2", game="Quake III Arena", players_max=4, created_by="0x2")
    )
    session.commit()

    res = client.delete("/games/Quake III Arena", headers=headers)
    assert res.status_code == 409
    assert "2 active rooms" in res.json()["detail"]
    # Nothing deleted without force.
    assert "Quake III Arena" in client.get("/games").json()
    assert len(session.exec(select(Room)).all()) == 2


def test_admin_delete_game_force_closes_rooms(
    client: TestClient, session: Session, admin_headers
):
    headers, _ = admin_headers
    member = _create_user(session, "0xPlayer")
    room = Room(
        name="q3-x", game="Quake III Arena", players_max=4, created_by="0xPlayer"
    )
    room.members.append(member)
    session.add(room)
    session.commit()
    session.refresh(room)
    session.add(Message(room_id=room.id, sender_address="0xPlayer", content="x"))
    session.commit()

    res = client.delete("/games/Quake III Arena?force=true", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["rooms_closed"] == ["q3-x"]
    assert "Quake III Arena" not in client.get("/games").json()
    assert session.exec(select(Room)).all() == []
    assert session.exec(select(Message)).all() == []
    assert session.exec(select(RoomMember)).all() == []
