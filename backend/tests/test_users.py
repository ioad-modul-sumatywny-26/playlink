import os
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import User
from usernames import contains_profanity, load_stoplist, validate_username


def _mint_token(address: str) -> str:
    secret = os.environ["JWT_SECRET"]
    payload = {
        "sub": address,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "playlink-auth",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_user(session: Session, address: str, username: str | None = None) -> User:
    user = User(identity_address=address)
    if username is not None:
        user.username = username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --- unit: stoplist / validation -------------------------------------------


def test_stoplist_loads_non_empty():
    assert len(load_stoplist()) > 0


def test_contains_profanity_exact_and_case_insensitive():
    assert contains_profanity("fuck")
    assert contains_profanity("FUCK")


def test_contains_profanity_token_split():
    assert contains_profanity("xX_fuck_Xx")
    assert contains_profanity("pro-shit-gamer")


def test_contains_profanity_avoids_false_positives():
    # 'ass' substring appears but is not a standalone token
    assert not contains_profanity("assassin")
    assert not contains_profanity("classic_gamer")


def test_validate_username_rejects_format_and_profanity():
    assert validate_username("ab") == "invalid_format"  # too short
    assert validate_username("has spaces") == "invalid_format"
    assert validate_username("a" * 21) == "invalid_format"
    assert validate_username("fuck") == "profane"
    assert validate_username("CoolGamer_99") is None


# --- endpoint: PATCH /users/me ---------------------------------------------


def test_update_username_success(client: TestClient, session: Session):
    addr = "0xAbc0000000000000000000000000000000000001"
    _make_user(session, addr)
    token = _mint_token(addr)

    resp = client.patch(
        "/users/me",
        json={"username": "NightRaven_7"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "NightRaven_7"

    refreshed = session.exec(select(User).where(User.identity_address == addr)).first()
    assert refreshed.username == "NightRaven_7"


def test_update_username_idempotent_same_value(client: TestClient, session: Session):
    addr = "0xAbc0000000000000000000000000000000000002"
    _make_user(session, addr, username="StableName")
    token = _mint_token(addr)

    resp = client.patch(
        "/users/me",
        json={"username": "StableName"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "StableName"


def test_update_username_invalid_format(client: TestClient, session: Session):
    addr = "0xAbc0000000000000000000000000000000000003"
    _make_user(session, addr)
    token = _mint_token(addr)

    resp = client.patch(
        "/users/me",
        json={"username": "no"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_update_username_profane(client: TestClient, session: Session):
    addr = "0xAbc0000000000000000000000000000000000004"
    _make_user(session, addr)
    token = _mint_token(addr)

    resp = client.patch(
        "/users/me",
        json={"username": "FuCk"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_update_username_conflict(client: TestClient, session: Session):
    taken_addr = "0xAbc0000000000000000000000000000000000005"
    mine_addr = "0xAbc0000000000000000000000000000000000006"
    _make_user(session, taken_addr, username="Taken_Name")
    _make_user(session, mine_addr)
    token = _mint_token(mine_addr)

    resp = client.patch(
        "/users/me",
        json={"username": "Taken_Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_update_username_unauthenticated(client: TestClient):
    resp = client.patch("/users/me", json={"username": "Whoever"})
    assert resp.status_code == 401
