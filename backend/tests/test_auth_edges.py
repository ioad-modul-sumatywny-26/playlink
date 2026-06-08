import os
from datetime import UTC, datetime, timedelta

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import main
from models import Nonce, User


def _sign_nonce(account, nonce: str) -> str:
    message = encode_defunct(text=f"Sign in to Playlink\nNonce: {nonce}")
    return account.sign_message(message).signature.hex()


def _mint_token(
    address: str | None,
    *,
    expires_delta: timedelta = timedelta(minutes=5),
    extra: dict | None = None,
) -> str:
    payload = {
        "username": "tester",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + expires_delta,
        "iss": "playlink-auth",
    }
    if address is not None:
        payload["sub"] = address
    if extra:
        payload.update(extra)
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def test_request_nonce_stores_hash_and_invalidates_previous_nonce(
    client: TestClient, session: Session
):
    account = Account.create()

    first = client.post("/auth/request-nonce", params={"address": account.address})
    assert first.status_code == 200
    first_nonce = first.json()["nonce"]

    second = client.post("/auth/request-nonce", params={"address": account.address})
    assert second.status_code == 200
    second_nonce = second.json()["nonce"]

    rows = session.exec(
        select(Nonce).where(Nonce.identity_address == account.address)
    ).all()
    rows = sorted(rows, key=lambda row: row.id)

    assert [row.value for row in rows] == [
        main.hash_nonce(first_nonce),
        main.hash_nonce(second_nonce),
    ]
    assert rows[0].used is True
    assert rows[1].used is False
    assert first_nonce not in {row.value for row in rows}
    assert second_nonce not in {row.value for row in rows}


def test_verify_signature_rejects_replayed_nonce(client: TestClient, session: Session):
    account = Account.create()
    nonce = client.post(
        "/auth/request-nonce", params={"address": account.address}
    ).json()["nonce"]
    signature = _sign_nonce(account, nonce)

    first = client.post(
        "/auth/verify",
        json={"address": account.address, "nonce": nonce, "signature": signature},
    )
    assert first.status_code == 200

    replay = client.post(
        "/auth/verify",
        json={"address": account.address, "nonce": nonce, "signature": signature},
    )
    assert replay.status_code == 401
    assert replay.json()["detail"] == "Invalid or expired challenge"

    db_nonce = session.exec(select(Nonce)).one()
    assert db_nonce.used is True


def test_verify_signature_rejects_expired_nonce(client: TestClient, session: Session):
    account = Account.create()
    nonce = client.post(
        "/auth/request-nonce", params={"address": account.address}
    ).json()["nonce"]

    db_nonce = session.exec(
        select(Nonce).where(Nonce.value == main.hash_nonce(nonce))
    ).one()
    db_nonce.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(db_nonce)
    session.commit()

    response = client.post(
        "/auth/verify",
        json={
            "address": account.address,
            "nonce": nonce,
            "signature": _sign_nonce(account, nonce),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired challenge"


def test_verify_signature_rejects_invalid_signature_format(client: TestClient):
    account = Account.create()
    nonce = client.post(
        "/auth/request-nonce", params={"address": account.address}
    ).json()["nonce"]

    response = client.post(
        "/auth/verify",
        json={
            "address": account.address,
            "nonce": nonce,
            "signature": "not-a-signature",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature format"


def test_verify_signature_rejects_invalid_address_format(client: TestClient):
    response = client.post(
        "/auth/verify",
        json={"address": "bad-address", "nonce": "n", "signature": "s"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid identity address format"


def test_get_me_rejects_expired_token(client: TestClient, session: Session):
    address = Account.create().address
    session.add(User(identity_address=address))
    session.commit()
    token = _mint_token(address, expires_delta=timedelta(seconds=-1))

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_get_me_rejects_token_without_subject(client: TestClient):
    token = _mint_token(None)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_get_me_rejects_token_for_missing_user(client: TestClient):
    token = _mint_token(Account.create().address)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_forged_admin_claim_does_not_grant_admin_access(client: TestClient):
    address = Account.create().address
    main.ADMIN_ADDRESSES.discard(address.lower())
    token = _mint_token(address, extra={"is_admin": True})

    response = client.post(
        "/games",
        json={"name": "Doom"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"
