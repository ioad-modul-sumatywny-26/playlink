from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import User


def test_request_nonce(client: TestClient):
    # Create a random account
    acct = Account.create()
    address = acct.address

    response = client.post("/auth/request-nonce", params={"address": address})
    assert response.status_code == 200
    data = response.json()
    assert "nonce" in data
    assert isinstance(data["nonce"], str)


def test_request_nonce_invalid_address(client: TestClient):
    response = client.post("/auth/request-nonce", params={"address": "invalid-address"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid identity address format"


def test_verify_signature_success(client: TestClient, session: Session):
    # Create a random account
    acct = Account.create()
    address = acct.address

    # 1. Request nonce
    response = client.post("/auth/request-nonce", params={"address": address})
    nonce = response.json()["nonce"]

    # 2. Sign the message
    message_text = f"Sign in to Playlink\nNonce: {nonce}"
    message = encode_defunct(text=message_text)
    signed_message = acct.sign_message(message)
    signature = signed_message.signature.hex()

    # 3. Verify signature
    response = client.post(
        "/auth/verify",
        params={"address": address, "nonce": nonce, "signature": signature},
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    # Check if nonce is marked as used
    # Note: We need to use the session to check the DB
    # But since we use a shared session in conftest, it should work
    db_user = session.exec(select(User).where(User.identity_address == address)).first()
    assert db_user is not None
    assert db_user.last_login is not None


def test_verify_signature_invalid_nonce(client: TestClient):
    acct = Account.create()
    address = acct.address

    # Sign with a nonce that doesn't exist in DB
    nonce = "wrong-nonce"
    message_text = f"Sign in to Playlink\nNonce: {nonce}"
    message = encode_defunct(text=message_text)
    signature = acct.sign_message(message).signature.hex()

    response = client.post(
        "/auth/verify",
        params={"address": address, "nonce": nonce, "signature": signature},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired challenge"


def test_verify_signature_wrong_signer(client: TestClient):
    acct1 = Account.create()
    acct2 = Account.create()  # Wrong signer

    # 1. Request nonce for acct1
    response = client.post("/auth/request-nonce", params={"address": acct1.address})
    nonce = response.json()["nonce"]

    # 2. Sign for acct1 but with acct2's key
    message_text = f"Sign in to Playlink\nNonce: {nonce}"
    message = encode_defunct(text=message_text)
    signature = acct2.sign_message(message).signature.hex()

    # 3. Verify
    response = client.post(
        "/auth/verify",
        params={"address": acct1.address, "nonce": nonce, "signature": signature},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Identity verification failed"


def test_nonce_invalidation(client: TestClient):
    acct = Account.create()
    address = acct.address

    # 1. Request first nonce
    resp1 = client.post("/auth/request-nonce", params={"address": address})
    nonce1 = resp1.json()["nonce"]

    # 2. Request second nonce (should invalidate first)
    resp2 = client.post("/auth/request-nonce", params={"address": address})
    nonce2 = resp2.json()["nonce"]

    # 3. Try to verify with first nonce (should fail)
    message_text1 = f"Sign in to Playlink\nNonce: {nonce1}"
    signature1 = acct.sign_message(encode_defunct(text=message_text1)).signature.hex()

    response1 = client.post(
        "/auth/verify",
        params={"address": address, "nonce": nonce1, "signature": signature1},
    )
    assert response1.status_code == 401

    # 4. Try to verify with second nonce (should succeed)
    message_text2 = f"Sign in to Playlink\nNonce: {nonce2}"
    signature2 = acct.sign_message(encode_defunct(text=message_text2)).signature.hex()

    response2 = client.post(
        "/auth/verify",
        params={"address": address, "nonce": nonce2, "signature": signature2},
    )
    assert response2.status_code == 200
