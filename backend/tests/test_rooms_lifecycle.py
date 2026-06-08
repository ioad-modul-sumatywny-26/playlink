import os
from datetime import UTC, datetime, timedelta

import jwt
from eth_account import Account
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Room, User


def _mint_token(address: str) -> str:
    payload = {
        "sub": address,
        "username": "tester",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def _auth_headers(address: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint_token(address)}"}


def _create_user(session: Session, address: str) -> User:
    user = User(identity_address=address)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed_room(
    session: Session,
    name: str,
    creator: str,
    *,
    members: list[str] | None = None,
    players_max: int = 4,
    game: str = "Quake III Arena",
) -> Room:
    member_addresses = members if members is not None else [creator]
    users = [_create_user(session, address) for address in member_addresses]
    room = Room(name=name, game=game, players_max=players_max, created_by=creator)
    room.members.extend(users)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room


def _room_body(name: str, *, game: str = "Quake III Arena") -> dict:
    return {
        "name": name,
        "game": game,
        "lobby_location": "eu-central",
        "players_max": 4,
    }


def test_create_room_requires_auth(client: TestClient):
    response = client.post("/rooms", json=_room_body("auth-required"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_get_missing_room_returns_404(client: TestClient):
    response = client.get("/rooms/no-such-room")

    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"


def test_create_room_rejects_blank_game_after_trimming(
    client: TestClient, session: Session
):
    address = Account.create().address
    _create_user(session, address)

    response = client.post(
        "/rooms",
        json=_room_body("blank-game", game="   "),
        headers=_auth_headers(address),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Game name is required"


def test_create_room_rejects_duplicate_name(client: TestClient, session: Session):
    address = Account.create().address
    _create_user(session, address)
    headers = _auth_headers(address)

    first = client.post("/rooms", json=_room_body("dupe"), headers=headers)
    second = client.post("/rooms", json=_room_body("dupe"), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Room name already taken"


def test_create_room_enforces_three_room_limit(client: TestClient, session: Session):
    address = Account.create().address
    _create_user(session, address)
    headers = _auth_headers(address)

    for index in range(3):
        response = client.post(
            "/rooms", json=_room_body(f"room-{index}"), headers=headers
        )
        assert response.status_code == 201

    response = client.post("/rooms", json=_room_body("room-4"), headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "You can create a maximum of 3 rooms."


def test_create_room_auto_joins_creator(client: TestClient, session: Session):
    address = Account.create().address
    _create_user(session, address)

    response = client.post(
        "/rooms", json=_room_body("auto-join"), headers=_auth_headers(address)
    )
    assert response.status_code == 201

    room = client.get("/rooms/auto-join").json()
    assert room["players_active"] == 1
    assert room["member_addresses"] == [address]
    assert room["members"][0]["address"] == address


def test_join_room_rejects_missing_room(client: TestClient, session: Session):
    address = Account.create().address
    _create_user(session, address)

    response = client.post("/rooms/missing/join", headers=_auth_headers(address))

    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"


def test_join_room_rejects_missing_user(client: TestClient, session: Session):
    creator = Account.create().address
    _seed_room(session, "lobby", creator)
    unknown_user = Account.create().address

    response = client.post("/rooms/lobby/join", headers=_auth_headers(unknown_user))

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_join_room_rejects_existing_member(client: TestClient, session: Session):
    creator = Account.create().address
    _seed_room(session, "lobby", creator)

    response = client.post("/rooms/lobby/join", headers=_auth_headers(creator))

    assert response.status_code == 400
    assert response.json()["detail"] == "You are already in this room"


def test_join_room_rejects_full_room(client: TestClient, session: Session):
    creator = Account.create().address
    joiner = Account.create().address
    _seed_room(session, "full", creator, players_max=1)
    _create_user(session, joiner)

    response = client.post("/rooms/full/join", headers=_auth_headers(joiner))

    assert response.status_code == 400
    assert response.json()["detail"] == "Room is full"


def test_join_room_adds_member_to_room_payload(client: TestClient, session: Session):
    creator = Account.create().address
    joiner = Account.create().address
    _seed_room(session, "joinable", creator)
    _create_user(session, joiner)

    response = client.post("/rooms/joinable/join", headers=_auth_headers(joiner))
    assert response.status_code == 200

    room = client.get("/rooms/joinable").json()
    assert room["players_active"] == 2
    assert room["member_addresses"] == [creator, joiner]


def test_leave_room_rejects_missing_room(client: TestClient, session: Session):
    address = Account.create().address
    _create_user(session, address)

    response = client.post("/rooms/missing/leave", headers=_auth_headers(address))

    assert response.status_code == 404
    assert response.json()["detail"] == "Room not found"


def test_leave_room_rejects_missing_user(client: TestClient, session: Session):
    creator = Account.create().address
    _seed_room(session, "lobby", creator)
    unknown_user = Account.create().address

    response = client.post("/rooms/lobby/leave", headers=_auth_headers(unknown_user))

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_leave_room_rejects_non_member(client: TestClient, session: Session):
    creator = Account.create().address
    outsider = Account.create().address
    _seed_room(session, "lobby", creator)
    _create_user(session, outsider)

    response = client.post("/rooms/lobby/leave", headers=_auth_headers(outsider))

    assert response.status_code == 400
    assert response.json()["detail"] == "You are not in this room"


def test_leave_room_removes_member_from_room_payload(
    client: TestClient, session: Session
):
    creator = Account.create().address
    member = Account.create().address
    _seed_room(session, "leavable", creator, members=[creator, member])

    response = client.post("/rooms/leavable/leave", headers=_auth_headers(member))
    assert response.status_code == 200

    room = client.get("/rooms/leavable").json()
    assert room["players_active"] == 1
    assert room["member_addresses"] == [creator]

    persisted = session.exec(select(Room).where(Room.name == "leavable")).one()
    assert [user.identity_address for user in persisted.members] == [creator]
