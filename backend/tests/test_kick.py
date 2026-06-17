import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

import main
from models import Message, Room, RoomEvent, RoomEventRsvp, User


def _token(address: str, *, is_admin: bool = False) -> str:
    return jwt.encode(
        {
            "sub": address,
            "username": "tester",
            "is_admin": is_admin,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iss": "playlink-auth",
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


def _headers(address: str, *, is_admin: bool = False) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(address, is_admin=is_admin)}"}


def _seed_room(session: Session, name: str, addresses: list[str]) -> Room:
    users = [
        User(identity_address=address, username=f"player_{index}")
        for index, address in enumerate(addresses)
    ]
    session.add_all(users)
    session.commit()
    room = Room(
        name=name,
        game="Quake III Arena",
        players_max=8,
        created_by=addresses[0],
    )
    room.members.extend(users)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room


@pytest.fixture
def admin_address():
    address = "0xAdmin"
    main.ADMIN_ADDRESSES.add(address.lower())
    try:
        yield address
    finally:
        main.ADMIN_ADDRESSES.discard(address.lower())


def test_kick_requires_admin(client: TestClient, session: Session):
    _seed_room(session, "lobby", ["0xOwner", "0xMember"])

    unauthenticated = client.post("/rooms/lobby/members/0xMember/kick")
    regular = client.post(
        "/rooms/lobby/members/0xMember/kick", headers=_headers("0xOwner")
    )

    assert unauthenticated.status_code == 401
    assert regular.status_code == 403


def test_admin_cannot_kick_an_admin(
    client: TestClient, session: Session, admin_address: str
):
    other_admin = "0xOtherAdmin"
    main.ADMIN_ADDRESSES.add(other_admin.lower())
    try:
        _seed_room(session, "lobby", [admin_address, other_admin])
        response = client.post(
            f"/rooms/lobby/members/{other_admin}/kick",
            headers=_headers(admin_address, is_admin=True),
        )
    finally:
        main.ADMIN_ADDRESSES.discard(other_admin.lower())

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrators cannot be kicked"


def test_kick_removes_member_rsvp_and_allows_rejoin(
    client: TestClient, session: Session, admin_address: str
):
    target_address = "0xTarget"
    room = _seed_room(session, "lobby", [admin_address, target_address])
    target = session.exec(
        select(User).where(User.identity_address == target_address)
    ).one()
    event = RoomEvent(
        room_id=room.id,
        starts_at=datetime.now(UTC) + timedelta(hours=1),
        ends_at=datetime.now(UTC) + timedelta(hours=2),
        created_by=admin_address,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    session.add(RoomEventRsvp(event_id=event.id, user_id=target.id, status="present"))
    session.commit()

    response = client.post(
        f"/rooms/lobby/members/{target_address.lower()}/kick",
        headers=_headers(admin_address, is_admin=True),
    )

    assert response.status_code == 200
    assert response.json()["member_address"] == target_address
    session.refresh(room)
    assert [member.identity_address for member in room.members] == [admin_address]
    assert session.exec(select(RoomEventRsvp)).all() == []
    system_message = session.exec(select(Message)).one()
    assert system_message.sender_address == main.SYSTEM_SENDER_ADDRESS
    assert system_message.content == (
        "player_1 was removed from the room by an administrator."
    )

    rejoin = client.post("/rooms/lobby/join", headers=_headers(target_address))
    assert rejoin.status_code == 200
    assert rejoin.json()["status"] == "joined"

    with client.websocket_connect(
        f"/ws/rooms/lobby/chat?token={_token(target_address)}"
    ) as websocket:
        history = websocket.receive_json()
        assert history["messages"][0]["kind"] == "system"


def test_kicking_creator_transfers_ownership_without_restoring_it_on_rejoin(
    client: TestClient, session: Session, admin_address: str
):
    creator = "0xCreator"
    room = _seed_room(session, "lobby", [creator, admin_address])

    response = client.post(
        f"/rooms/lobby/members/{creator}/kick",
        headers=_headers(admin_address, is_admin=True),
    )

    assert response.status_code == 200
    assert response.json()["ownership_transferred"] is True
    assert response.json()["created_by"] == admin_address
    session.refresh(room)
    assert room.created_by == admin_address

    rejoin = client.post("/rooms/lobby/join", headers=_headers(creator))
    assert rejoin.status_code == 200
    session.refresh(room)
    assert room.created_by == admin_address


def test_kick_notifies_and_disconnects_active_socket(
    client: TestClient, session: Session, admin_address: str
):
    target = "0xTarget"
    _seed_room(session, "lobby", [admin_address, target])

    websocket_url = f"/ws/rooms/lobby/chat?token={_token(target)}"
    with (
        client.websocket_connect(websocket_url) as first_socket,
        client.websocket_connect(websocket_url) as second_socket,
    ):
        assert first_socket.receive_json()["type"] == "history"
        assert second_socket.receive_json()["type"] == "history"
        response = client.post(
            f"/rooms/lobby/members/{target}/kick",
            headers=_headers(admin_address, is_admin=True),
        )
        assert response.status_code == 200
        for websocket in (first_socket, second_socket):
            assert websocket.receive_json()["message"]["kind"] == "system"
            assert websocket.receive_json()["type"] == "roster_update"
            kicked = websocket.receive_json()
            assert kicked["type"] == "member_kicked"
            assert kicked["member_address"] == target
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 4409


def test_room_member_payload_marks_admins(
    client: TestClient, session: Session, admin_address: str
):
    _seed_room(session, "lobby", [admin_address, "0xMember"])

    members = client.get("/rooms/lobby").json()["members"]

    assert members == [
        {"address": admin_address, "username": "player_0", "is_admin": True},
        {"address": "0xMember", "username": "player_1", "is_admin": False},
    ]
