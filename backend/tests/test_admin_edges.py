import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import main
from models import Room, User


def _mint_token(address: str, *, is_admin: bool = False) -> str:
    payload = {
        "sub": address,
        "username": "tester",
        "is_admin": is_admin,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest.fixture
def admin_headers():
    address = Account.create().address
    main.ADMIN_ADDRESSES.add(address.lower())
    try:
        yield {"Authorization": f"Bearer {_mint_token(address, is_admin=True)}"}
    finally:
        main.ADMIN_ADDRESSES.discard(address.lower())


def _create_user(session: Session, address: str) -> User:
    user = User(identity_address=address)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed_room(session: Session, name: str, member_address: str) -> Room:
    member = _create_user(session, member_address)
    room = Room(
        name=name,
        game="Quake III Arena",
        players_max=4,
        created_by=member_address,
    )
    room.members.append(member)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room


def test_admin_create_game_trims_name_before_persisting(
    client: TestClient, admin_headers
):
    response = client.post("/games", json={"name": "  DOOM  "}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["name"] == "DOOM"
    games = client.get("/games").json()
    assert "DOOM" in games
    assert "  DOOM  " not in games


def test_force_delete_game_closes_each_active_room_over_chat_ws(
    client: TestClient, session: Session, admin_headers
):
    first_member = Account.create().address
    second_member = Account.create().address
    _seed_room(session, "q3-one", first_member)
    _seed_room(session, "q3-two", second_member)

    first_token = _mint_token(first_member)
    second_token = _mint_token(second_member)
    with (
        client.websocket_connect(f"/ws/rooms/q3-one/chat?token={first_token}") as ws_a,
        client.websocket_connect(f"/ws/rooms/q3-two/chat?token={second_token}") as ws_b,
    ):
        assert ws_a.receive_json()["type"] == "history"
        assert ws_b.receive_json()["type"] == "history"

        response = client.delete(
            "/games/Quake III Arena?force=true", headers=admin_headers
        )
        assert response.status_code == 200
        assert set(response.json()["rooms_closed"]) == {"q3-one", "q3-two"}

        assert ws_a.receive_json() == {"type": "room_closed", "room": "q3-one"}
        assert ws_b.receive_json() == {"type": "room_closed", "room": "q3-two"}

    assert session.exec(select(Room)).all() == []
