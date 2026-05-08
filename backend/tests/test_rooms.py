import os
from datetime import UTC, datetime, timedelta

import jwt
from eth_account import Account
from fastapi.testclient import TestClient
from sqlmodel import Session


def _auth_headers() -> tuple[dict[str, str], str]:
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


def _create_user(session: Session, address: str) -> None:
    from models import User

    session.add(User(identity_address=address))
    session.commit()


def test_create_room_with_metadata(client: TestClient, session: Session):
    headers, address = _auth_headers()
    _create_user(session, address)

    body = {
        "name": "lobby-1",
        "game": "Quake III Arena",
        "players_max": 4,
        "description": "Friday rocket arena, casual",
        "communicator_link": "https://discord.gg/example",
        "requirements": "CPMA mod, latest patch",
    }
    res = client.post("/rooms", json=body, headers=headers)
    assert res.status_code == 201

    res = client.get("/rooms/lobby-1")
    assert res.status_code == 200
    data = res.json()
    assert data["description"] == body["description"]
    assert data["communicator_link"] == "https://discord.gg/example"
    assert data["requirements"] == body["requirements"]


def test_create_room_without_metadata_returns_nulls(
    client: TestClient, session: Session
):
    headers, address = _auth_headers()
    _create_user(session, address)

    body = {"name": "lobby-2", "game": "Diablo II", "players_max": 8}
    res = client.post("/rooms", json=body, headers=headers)
    assert res.status_code == 201

    res = client.get("/rooms/lobby-2")
    assert res.status_code == 200
    data = res.json()
    assert data["description"] is None
    assert data["communicator_link"] is None
    assert data["requirements"] is None


def test_create_room_rejects_invalid_communicator_url(
    client: TestClient, session: Session
):
    headers, address = _auth_headers()
    _create_user(session, address)

    body = {
        "name": "lobby-3",
        "game": "StarCraft",
        "players_max": 2,
        "communicator_link": "not a url",
    }
    res = client.post("/rooms", json=body, headers=headers)
    assert res.status_code == 422


def test_create_room_rejects_oversized_description(
    client: TestClient, session: Session
):
    headers, address = _auth_headers()
    _create_user(session, address)

    body = {
        "name": "lobby-4",
        "game": "Half-Life",
        "players_max": 4,
        "description": "x" * 501,
    }
    res = client.post("/rooms", json=body, headers=headers)
    assert res.status_code == 422


def test_list_rooms_includes_metadata(client: TestClient, session: Session):
    headers, address = _auth_headers()
    _create_user(session, address)

    body = {
        "name": "lobby-5",
        "game": "Unreal Tournament",
        "players_max": 6,
        "description": "shown in list",
        "communicator_link": "https://example.com/chat",
        "requirements": "mouse + keyboard",
    }
    client.post("/rooms", json=body, headers=headers)

    res = client.get("/rooms")
    assert res.status_code == 200
    rooms = res.json()
    target = next(r for r in rooms if r["name"] == "lobby-5")
    assert target["description"] == "shown in list"
    assert target["communicator_link"] == "https://example.com/chat"
    assert target["requirements"] == "mouse + keyboard"
