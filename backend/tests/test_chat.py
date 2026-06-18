import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from models import Message, Room, User


def _mint_token(address: str) -> str:
    secret = os.environ["JWT_SECRET"]
    payload = {
        "sub": address,
        "username": "tester",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _all(session: Session, statement):
    return session.exec(statement).all()


def _seed_room_and_users(session: Session, room_name: str, members: list[str]) -> Room:
    user_objs = []
    for addr in members:
        u = User(identity_address=addr)
        session.add(u)
        user_objs.append(u)
    session.commit()
    for u in user_objs:
        session.refresh(u)

    room = Room(
        name=room_name,
        game="Quake III Arena",
        players_max=4,
        created_by=members[0],
    )
    room.members.extend(user_objs)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room


def test_chat_rejects_bad_token(client: TestClient, session: Session):
    _seed_room_and_users(session, "r1", ["0xabc"])
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/ws/rooms/r1/chat?token=garbage"),
    ):
        pass
    assert exc.value.code == 4401


def test_chat_rejects_non_member(client: TestClient, session: Session):
    _seed_room_and_users(session, "r2", ["0xMember"])
    outsider = "0xOutsider"
    session.add(User(identity_address=outsider))
    session.commit()
    token = _mint_token(outsider)
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(f"/ws/rooms/r2/chat?token={token}"),
    ):
        pass
    assert exc.value.code == 4403


def test_chat_rejects_missing_room(client: TestClient, session: Session):
    addr = "0xLone"
    session.add(User(identity_address=addr))
    session.commit()
    token = _mint_token(addr)
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(f"/ws/rooms/nope/chat?token={token}"),
    ):
        pass
    assert exc.value.code == 4404


def test_chat_broadcast_between_members(client: TestClient, session: Session):
    a, b = "0xAlice", "0xBob"
    _seed_room_and_users(session, "lobby", [a, b])
    ta, tb = _mint_token(a), _mint_token(b)

    with (
        client.websocket_connect(f"/ws/rooms/lobby/chat?token={ta}") as ws_a,
        client.websocket_connect(f"/ws/rooms/lobby/chat?token={tb}") as ws_b,
    ):
        history_a = ws_a.receive_json()
        history_b = ws_b.receive_json()
        assert history_a == {"type": "history", "messages": []}
        assert history_b == {"type": "history", "messages": []}

        ws_a.send_json({"content": "hello world"})

        msg_a = ws_a.receive_json()
        msg_b = ws_b.receive_json()
        assert msg_a["type"] == "message"
        assert msg_b["type"] == "message"
        assert msg_a["message"]["content"] == "hello world"
        assert msg_a["message"]["sender_address"] == a
        assert msg_b["message"]["content"] == "hello world"

    rows = _all(session, select(Message))
    assert len(rows) == 1
    assert rows[0].content == "hello world"


def test_chat_history_replay(client: TestClient, session: Session):
    addr = "0xSolo"
    _seed_room_and_users(session, "echoes", [addr])
    token = _mint_token(addr)

    with client.websocket_connect(f"/ws/rooms/echoes/chat?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"content": "first"})
        ws.receive_json()
        ws.send_json({"content": "second"})
        ws.receive_json()

    with client.websocket_connect(f"/ws/rooms/echoes/chat?token={token}") as ws:
        history = ws.receive_json()
        assert history["type"] == "history"
        contents = [m["content"] for m in history["messages"]]
        assert contents == ["first", "second"]


def test_chat_drops_oversize_and_empty(client: TestClient, session: Session):
    addr = "0xWriter"
    _seed_room_and_users(session, "limited", [addr])
    token = _mint_token(addr)

    with client.websocket_connect(f"/ws/rooms/limited/chat?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"content": "   "})
        ws.send_json({"content": "x" * 1001})
        ws.send_json({"content": "kept"})
        msg = ws.receive_json()
        assert msg["message"]["content"] == "kept"

    rows = _all(session, select(Message))
    assert [r.content for r in rows] == ["kept"]


# --- Cryptographically signed messages (issue #59) ---------------------------


def _canonical_chat(room: str, content: str, sent_at: str) -> str:
    """Mirror of the backend's canonical signing payload. Must stay in sync."""
    return (
        "PlayLink signed chat message\n"
        f"room={room}\n"
        f"sent_at={sent_at}\n"
        f"content={content}"
    )


def _sign_chat(acct, room: str, content: str, sent_at: str) -> str:
    message = encode_defunct(text=_canonical_chat(room, content, sent_at))
    return acct.sign_message(message).signature.hex()


def _seed_signed_member(session: Session, room_name: str):
    """Seed a room whose sole member owns a real keypair; return (acct, token)."""
    acct = Account.create()
    _seed_room_and_users(session, room_name, [acct.address])
    return acct, _mint_token(acct.address)


def test_chat_signed_message_is_verified(client: TestClient, session: Session):
    acct, token = _seed_signed_member(session, "vault")
    sent_at = datetime.now(UTC).isoformat()
    content = "signed hello"
    sig = _sign_chat(acct, "vault", content, sent_at)

    with client.websocket_connect(f"/ws/rooms/vault/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": content, "sent_at": sent_at, "signature": sig})
        frame = ws.receive_json()

    assert frame["type"] == "message"
    msg = frame["message"]
    assert msg["content"] == content
    assert msg["verified"] is True
    assert msg["signature"] == sig
    assert msg["sent_at"] == sent_at

    rows = _all(session, select(Message))
    assert len(rows) == 1
    assert rows[0].signature == sig
    assert rows[0].sent_at == sent_at


def test_chat_rejects_tampered_content(client: TestClient, session: Session):
    acct, token = _seed_signed_member(session, "tamper")
    sent_at = datetime.now(UTC).isoformat()
    sig = _sign_chat(acct, "tamper", "original", sent_at)

    with client.websocket_connect(f"/ws/rooms/tamper/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": "modified", "sent_at": sent_at, "signature": sig})
        frame = ws.receive_json()

    assert frame["type"] == "error"
    assert frame["detail"] == "signature_invalid"
    assert _all(session, select(Message)) == []


def test_chat_rejects_wrong_signer(client: TestClient, session: Session):
    acct, token = _seed_signed_member(session, "imposter")
    attacker = Account.create()
    sent_at = datetime.now(UTC).isoformat()
    content = "not really me"
    sig = _sign_chat(attacker, "imposter", content, sent_at)

    with client.websocket_connect(f"/ws/rooms/imposter/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": content, "sent_at": sent_at, "signature": sig})
        frame = ws.receive_json()

    assert frame["type"] == "error"
    assert frame["detail"] == "signature_invalid"
    assert _all(session, select(Message)) == []


def test_chat_rejects_stale_timestamp(client: TestClient, session: Session):
    acct, token = _seed_signed_member(session, "stale")
    sent_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    content = "old news"
    sig = _sign_chat(acct, "stale", content, sent_at)

    with client.websocket_connect(f"/ws/rooms/stale/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": content, "sent_at": sent_at, "signature": sig})
        frame = ws.receive_json()

    assert frame["type"] == "error"
    assert frame["detail"] == "signature_invalid"
    assert _all(session, select(Message)) == []


def test_chat_unsigned_message_is_unverified(client: TestClient, session: Session):
    _, token = _seed_signed_member(session, "legacy")

    with client.websocket_connect(f"/ws/rooms/legacy/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": "plain text"})
        frame = ws.receive_json()

    msg = frame["message"]
    assert msg["content"] == "plain text"
    assert msg["verified"] is False
    assert msg["signature"] is None

    rows = _all(session, select(Message))
    assert len(rows) == 1
    assert rows[0].signature is None


def test_chat_history_includes_signature(client: TestClient, session: Session):
    acct, token = _seed_signed_member(session, "archive")
    sent_at = datetime.now(UTC).isoformat()
    content = "for the record"
    sig = _sign_chat(acct, "archive", content, sent_at)

    with client.websocket_connect(f"/ws/rooms/archive/chat?token={token}") as ws:
        ws.receive_json()  # history
        ws.send_json({"content": content, "sent_at": sent_at, "signature": sig})
        ws.receive_json()  # echoed message

    with client.websocket_connect(f"/ws/rooms/archive/chat?token={token}") as ws:
        history = ws.receive_json()

    assert history["type"] == "history"
    assert len(history["messages"]) == 1
    hm = history["messages"][0]
    assert hm["verified"] is True
    assert hm["signature"] == sig
