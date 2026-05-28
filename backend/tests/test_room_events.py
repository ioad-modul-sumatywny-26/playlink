"""Tests for the scheduled-event + RSVP feature on rooms (issue #62)."""

import json
import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import Room, RoomEvent, RoomEventRsvp, RsvpStatus, User

# ---------- helpers ----------


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


def _auth_headers(address: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint_token(address)}"}


def _seed_room(
    session: Session,
    room_name: str,
    members: list[str],
    *,
    expires_in_minutes: int = 60,
) -> Room:
    """Create users + a room with `members[0]` as creator and everyone joined."""
    user_objs: list[User] = []
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
        expires_at=datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
    )
    room.members.extend(user_objs)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room


def _future_iso(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def _event_body(start_minutes: int, duration_minutes: int = 120) -> dict[str, str]:
    """Standard PUT /event body with sensible defaults."""
    return {
        "starts_at": _future_iso(start_minutes),
        "ends_at": _future_iso(start_minutes + duration_minutes),
    }


# ---------- PUT /rooms/{name}/event ----------


def test_creator_can_schedule_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])

    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 200
    body = res.json()
    assert "starts_at" in body
    assert body["created_by"] == "0xCreator"
    assert body["rsvps"] == []

    persisted = session.exec(select(RoomEvent)).all()
    assert len(persisted) == 1


def test_non_creator_cannot_schedule_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])

    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xMember"),
    )
    assert res.status_code == 403
    assert "creator" in res.json()["detail"].lower()


def test_outsider_cannot_schedule_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    # Outsider isn't even in the user table; treat like an unknown JWT subject.
    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xOutsider"),
    )
    assert res.status_code == 403


def test_schedule_event_rejects_past_start(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])

    body = {
        "starts_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        "ends_at": _future_iso(60),
    }
    res = client.put(
        "/rooms/lobby-1/event",
        json=body,
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 400
    assert "future" in res.json()["detail"]


def test_schedule_event_extends_room_expiry_past_event_end(
    client: TestClient, session: Session
):
    """An event scheduled past the current room.expires_at pushes the room's
    expiry forward (with a grace period) so the room stays alive for the
    whole session.
    """
    room = _seed_room(session, "lobby-1", ["0xCreator"], expires_in_minutes=10)
    original_expiry = room.expires_at

    # Event ends 30 + 120 = 150 min from now, well past the 10-minute room.
    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 200

    session.refresh(room)
    new_expiry = room.expires_at
    if new_expiry.tzinfo is None:
        new_expiry = new_expiry.replace(tzinfo=UTC)
    if original_expiry.tzinfo is None:
        original_expiry = original_expiry.replace(tzinfo=UTC)
    assert new_expiry > original_expiry
    # Should be at least ends_at (start + 120 min).
    ends_at = datetime.now(UTC) + timedelta(minutes=30 + 120)
    assert new_expiry >= ends_at


def test_schedule_event_rejects_ends_before_starts(
    client: TestClient, session: Session
):
    _seed_room(session, "lobby-1", ["0xCreator"])

    body = {
        "starts_at": _future_iso(60),
        "ends_at": _future_iso(30),  # before start
    }
    res = client.put(
        "/rooms/lobby-1/event",
        json=body,
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 400
    assert "ends_at" in res.json()["detail"]


def test_schedule_event_for_missing_room_returns_404(client: TestClient):
    res = client.put(
        "/rooms/no-such-room/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 404


def test_schedule_event_is_idempotent_upsert(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])

    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 200
    first = res.json()

    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(45),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 200
    second = res.json()

    assert second["starts_at"] != first["starts_at"]
    # Still exactly one event row (no duplicate inserts).
    assert len(session.exec(select(RoomEvent)).all()) == 1


def test_rescheduling_event_clears_existing_rsvps(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xAlice", "0xBob"])

    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    for addr, status in [("0xAlice", "present"), ("0xBob", "maybe")]:
        res = client.put(
            "/rooms/lobby-1/event/rsvp",
            json={"status": status},
            headers=_auth_headers(addr),
        )
        assert res.status_code == 200

    pre = client.get("/rooms/lobby-1/event").json()
    assert len(pre["rsvps"]) == 2

    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(120),
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 200
    after = res.json()
    assert after["rsvps"] == []

    rsvp_rows = session.exec(select(RoomEventRsvp)).all()
    assert rsvp_rows == []


def test_rescheduling_event_with_identical_times_keeps_rsvps(
    client: TestClient, session: Session
):
    _seed_room(session, "lobby-1", ["0xCreator", "0xAlice"])

    body = _event_body(30)
    client.put("/rooms/lobby-1/event", json=body, headers=_auth_headers("0xCreator"))
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xAlice"),
    )

    res = client.put(
        "/rooms/lobby-1/event", json=body, headers=_auth_headers("0xCreator")
    )
    assert res.status_code == 200
    after = res.json()
    assert len(after["rsvps"]) == 1
    assert after["rsvps"][0]["status"] == "present"


def test_schedule_event_creator_match_is_case_insensitive(
    client: TestClient, session: Session
):
    # Room creator stored mixed-case; caller's JWT carries the same address
    # in lower case (e.g. coming from a different normalization path).
    _seed_room(session, "lobby-1", ["0xAbC123"])
    res = client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xabc123"),
    )
    assert res.status_code == 200


# ---------- GET /rooms/{name}/event ----------


def test_get_event_returns_404_when_unscheduled(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    res = client.get("/rooms/lobby-1/event")
    assert res.status_code == 404


def test_get_event_is_public_and_includes_rsvps(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])

    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    res = client.get("/rooms/lobby-1/event")  # no auth header on purpose
    assert res.status_code == 200
    body = res.json()
    assert body["created_by"] == "0xCreator"
    assert {r["address"]: r["status"] for r in body["rsvps"]} == {"0xMember": "present"}


def test_get_room_includes_event_field(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])

    res = client.get("/rooms/lobby-1")
    assert res.status_code == 200
    assert res.json()["event"] is None

    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    res = client.get("/rooms/lobby-1")
    assert res.status_code == 200
    assert res.json()["event"] is not None
    assert res.json()["event"]["created_by"] == "0xCreator"


# ---------- PUT /rooms/{name}/event/rsvp ----------


@pytest.mark.parametrize("status", ["present", "absent", "maybe"])
def test_member_can_set_each_rsvp_status(
    client: TestClient, session: Session, status: str
):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    res = client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": status},
        headers=_auth_headers("0xMember"),
    )
    assert res.status_code == 200
    assert res.json()["status"] == status


def test_rsvp_overwrites_previous_status(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    h = _auth_headers("0xMember")
    client.put("/rooms/lobby-1/event/rsvp", json={"status": "present"}, headers=h)
    client.put("/rooms/lobby-1/event/rsvp", json={"status": "maybe"}, headers=h)

    rows = session.exec(select(RoomEventRsvp)).all()
    assert len(rows) == 1
    assert rows[0].status == RsvpStatus.maybe


def test_outsider_cannot_rsvp(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    # Outsider with a valid token but no row in user table.
    res = client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xOutsider"),
    )
    # User not found → 404 (the endpoint resolves the user before membership).
    # We accept either 403 or 404 depending on how the principal is missing.
    assert res.status_code in (403, 404)


def test_rsvp_requires_existing_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    res = client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 404


def test_rsvp_rejects_invalid_status(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    res = client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "nope"},
        headers=_auth_headers("0xCreator"),
    )
    assert res.status_code == 422


# ---------- DELETE /rooms/{name}/event ----------


def test_creator_can_cancel_event_and_rsvps_are_cleared(
    client: TestClient, session: Session
):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    res = client.delete("/rooms/lobby-1/event", headers=_auth_headers("0xCreator"))
    assert res.status_code == 200

    assert session.exec(select(RoomEvent)).all() == []
    assert session.exec(select(RoomEventRsvp)).all() == []
    assert client.get("/rooms/lobby-1/event").status_code == 404


def test_non_creator_cannot_cancel_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    res = client.delete("/rooms/lobby-1/event", headers=_auth_headers("0xMember"))
    assert res.status_code == 403


def test_cancel_event_404_when_none(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator"])
    res = client.delete("/rooms/lobby-1/event", headers=_auth_headers("0xCreator"))
    assert res.status_code == 404


# ---------- leave_room interaction ----------


def test_leave_room_removes_users_rsvp(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    res = client.post("/rooms/lobby-1/leave", headers=_auth_headers("0xMember"))
    assert res.status_code == 200

    rsvp_rows = session.exec(select(RoomEventRsvp)).all()
    assert rsvp_rows == []
    body = client.get("/rooms/lobby-1/event").json()
    assert body["rsvps"] == []


# ---------- prune of expired rooms cleans events & rsvps ----------


def test_expired_room_is_pruned_with_event_and_rsvps(
    client: TestClient, session: Session
):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"], expires_in_minutes=60)
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    # Force the room to expire by rewriting its expires_at directly.
    room = session.exec(select(Room).where(Room.name == "lobby-1")).first()
    assert room is not None
    room.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(room)
    session.commit()

    # GET /rooms triggers get_rooms_payload, which prunes expired rooms.
    res = client.get("/rooms")
    assert res.status_code == 200

    # Pruning fires on the next mutation that calls get_rooms_payload, so
    # nudge it via the rooms-list WebSocket which sends the freshly built
    # payload immediately on connect.
    with client.websocket_connect("/ws/rooms") as ws:
        ws.receive_text()  # discard the initial snapshot

    # Now everything tied to the expired room should be gone.
    assert session.exec(select(Room)).all() == []
    assert session.exec(select(RoomEvent)).all() == []
    assert session.exec(select(RoomEventRsvp)).all() == []


# ---------- realtime broadcast over the chat WebSocket ----------


def test_schedule_event_broadcasts_event_update(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    creator_t = _mint_token("0xCreator")
    member_t = _mint_token("0xMember")

    with (
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws_a,
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={member_t}") as ws_b,
    ):
        ws_a.receive_json()  # history
        ws_b.receive_json()

        client.put(
            "/rooms/lobby-1/event",
            json=_event_body(30),
            headers=_auth_headers("0xCreator"),
        )

        for ws in (ws_a, ws_b):
            frame = ws.receive_json()
            assert frame["type"] == "event_update"
            assert frame["event"]["created_by"] == "0xCreator"
            assert frame["event"]["rsvps"] == []


def test_rsvp_update_broadcast(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    creator_t = _mint_token("0xCreator")
    member_t = _mint_token("0xMember")

    with (
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws_a,
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={member_t}") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        client.put(
            "/rooms/lobby-1/event/rsvp",
            json={"status": "maybe"},
            headers=_auth_headers("0xMember"),
        )

        for ws in (ws_a, ws_b):
            frame = ws.receive_json()
            assert frame["type"] == "rsvp_update"
            assert frame["rsvp"]["address"] == "0xMember"
            assert frame["rsvp"]["status"] == "maybe"


def test_join_broadcasts_roster_update(client: TestClient, session: Session):
    """A second member joining mid-session appears in the chat WS roster
    of an already-connected member."""
    _seed_room(session, "lobby-1", ["0xCreator"])
    creator_t = _mint_token("0xCreator")

    # Pre-create the joining user so the JWT subject resolves to a real user.
    new_user = User(identity_address="0xJoiner")
    session.add(new_user)
    session.commit()

    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws:
        ws.receive_json()  # history

        client.post("/rooms/lobby-1/join", headers=_auth_headers("0xJoiner"))

        frame = ws.receive_json()
        assert frame["type"] == "roster_update"
        addrs = [m["address"] for m in frame["members"]]
        assert "0xCreator" in addrs
        assert "0xJoiner" in addrs


def test_leave_broadcasts_roster_update(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    creator_t = _mint_token("0xCreator")

    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws:
        ws.receive_json()  # history

        client.post("/rooms/lobby-1/leave", headers=_auth_headers("0xMember"))

        frame = ws.receive_json()
        assert frame["type"] == "roster_update"
        addrs = [m["address"] for m in frame["members"]]
        assert addrs == ["0xCreator"]


def test_leave_with_rsvp_broadcasts_event_update(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    creator_t = _mint_token("0xCreator")
    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws_a:
        ws_a.receive_json()  # history

        client.post("/rooms/lobby-1/leave", headers=_auth_headers("0xMember"))

        # leave broadcasts roster_update first, then event_update because the
        # member had an RSVP that needs clearing.
        roster_frame = ws_a.receive_json()
        assert roster_frame["type"] == "roster_update"
        assert [m["address"] for m in roster_frame["members"]] == ["0xCreator"]

        event_frame = ws_a.receive_json()
        assert event_frame["type"] == "event_update"
        assert event_frame["event"]["rsvps"] == []


def test_cancel_event_broadcasts_null_event(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    creator_t = _mint_token("0xCreator")
    member_t = _mint_token("0xMember")
    with (
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={creator_t}") as ws_a,
        client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={member_t}") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        client.delete("/rooms/lobby-1/event", headers=_auth_headers("0xCreator"))

        for ws in (ws_a, ws_b):
            frame = ws.receive_json()
            assert frame["type"] == "event_update"
            assert frame["event"] is None


# ---------- regression: chat frames stay parseable ----------


def test_chat_history_and_message_frames_unchanged(
    client: TestClient, session: Session
):
    _seed_room(session, "lobby-1", ["0xCreator"])
    token = _mint_token("0xCreator")

    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={token}") as ws:
        history = ws.receive_json()
        assert history == {"type": "history", "messages": []}

        ws.send_json({"content": "hi"})
        msg = ws.receive_json()
        # No new top-level keys leaked into existing frames.
        assert set(msg.keys()) == {"type", "message"}
        assert msg["type"] == "message"
        assert set(msg["message"].keys()) == {
            "id",
            "sender_address",
            "sender_username",
            "content",
            "created_at",
        }


# ---------- defence-in-depth: payload shape ----------


def test_event_payload_shape(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )
    client.put(
        "/rooms/lobby-1/event/rsvp",
        json={"status": "present"},
        headers=_auth_headers("0xMember"),
    )

    body = client.get("/rooms/lobby-1/event").json()
    assert set(body.keys()) == {
        "starts_at",
        "ends_at",
        "created_by",
        "created_at",
        "updated_at",
        "rsvps",
    }
    rsvp = body["rsvps"][0]
    assert set(rsvp.keys()) == {"address", "username", "status", "updated_at"}

    # Same shape over WS.
    token = _mint_token("0xCreator")
    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={token}") as ws:
        ws.receive_json()  # history
        client.put(
            "/rooms/lobby-1/event",
            json=_event_body(45),
            headers=_auth_headers("0xCreator"),
        )
        frame = ws.receive_json()
        # Frame envelope plus the same event keys as REST.
        assert set(frame.keys()) == {"type", "event"}
        assert set(frame["event"].keys()) == {
            "starts_at",
            "ends_at",
            "created_by",
            "created_at",
            "updated_at",
            "rsvps",
        }


# Sanity check: ensure JSON serialization works the same as REST when payload
# is built off the same helper. This protects against silent drift.
def test_rest_and_ws_event_payloads_match(client: TestClient, session: Session):
    _seed_room(session, "lobby-1", ["0xCreator", "0xMember"])
    client.put(
        "/rooms/lobby-1/event",
        json=_event_body(30),
        headers=_auth_headers("0xCreator"),
    )

    token = _mint_token("0xCreator")
    with client.websocket_connect(f"/ws/rooms/lobby-1/chat?token={token}") as ws:
        ws.receive_json()  # history
        client.put(
            "/rooms/lobby-1/event/rsvp",
            json={"status": "present"},
            headers=_auth_headers("0xCreator"),
        )
        ws.receive_json()  # the rsvp_update frame, drop it
        client.put(
            "/rooms/lobby-1/event",
            json=_event_body(45),
            headers=_auth_headers("0xCreator"),
        )
        ws_frame = ws.receive_json()

    rest_payload = client.get("/rooms/lobby-1/event").json()
    # WS frame's `event` should match REST byte-for-byte (same helper).
    assert json.dumps(ws_frame["event"], sort_keys=True) == json.dumps(
        rest_payload, sort_keys=True
    )
