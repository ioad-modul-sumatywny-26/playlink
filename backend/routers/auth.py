"""Authentication: nonce challenge issuance and signature verification."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import select

from config import (
    DEFAULT_RATE_LIMIT,
    JWT_ALGORITHM,
    JWT_EXPIRATION_MINUTES,
    JWT_SECRET,
    NONCE_EXPIRATION_MINUTES,
    is_admin_address,
)
from dependencies import SessionDep
from models import Nonce, User
from rate_limit import limiter
from schemas import VerifyRequest
from security import hash_nonce

router = APIRouter(tags=["auth"])


@router.post("/auth/request-nonce")
@limiter.limit(DEFAULT_RATE_LIMIT)
def request_nonce(request: Request, address: str, session: SessionDep):  # noqa: ARG001
    """
    Request a one-time nonce for an identity address.
    """
    try:
        checksum_address = to_checksum_address(address)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid identity address format"
        ) from None

    # Upsert User
    user = session.exec(
        select(User).where(User.identity_address == checksum_address)
    ).first()
    if not user:
        user = User(identity_address=checksum_address)
        session.add(user)
        session.commit()
        session.refresh(user)

    # Generate & Hash Nonce
    nonce_value = str(uuid.uuid4())
    hashed_value = hash_nonce(nonce_value)

    # Invalidate previous unused nonces for this identity
    previous_nonces = session.exec(
        select(Nonce).where(
            Nonce.identity_address == checksum_address,
            Nonce.used == False,  # noqa: E712
        )
    ).all()
    for old_nonce in previous_nonces:
        old_nonce.used = True
        session.add(old_nonce)

    # Store new hashed nonce
    expires_at = datetime.now(UTC) + timedelta(minutes=NONCE_EXPIRATION_MINUTES)
    db_nonce = Nonce(
        identity_address=checksum_address,
        value=hashed_value,
        expires_at=expires_at,
        user_id=user.id,
    )
    session.add(db_nonce)
    session.commit()

    return {"nonce": nonce_value}


@router.post("/auth/verify")
@limiter.limit(DEFAULT_RATE_LIMIT)
def verify_signature(request: Request, body: VerifyRequest, session: SessionDep):  # noqa: ARG001
    """
    Verify signature against a nonce and issue a JWT.
    """
    address = body.address
    nonce = body.nonce
    signature = body.signature

    try:
        checksum_address = to_checksum_address(address)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid identity address format"
        ) from None

    hashed_provided_nonce = hash_nonce(nonce)

    # Fetch matching unused & unexpired nonce
    db_nonce = session.exec(
        select(Nonce).where(
            Nonce.identity_address == checksum_address,
            Nonce.value == hashed_provided_nonce,
            Nonce.used == False,  # noqa: E712
            Nonce.expires_at > datetime.now(UTC),
        )
    ).first()

    if not db_nonce:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge")

    # Recover address from signature
    message_text = f"Sign in to Playlink\nNonce: {nonce}"
    message = encode_defunct(text=message_text)

    try:
        recovered_address = Account.recover_message(message, signature=signature)
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid signature format"
        ) from None

    if recovered_address.lower() != checksum_address.lower():
        raise HTTPException(status_code=401, detail="Identity verification failed")

    # Success: Mark nonce as used & update user
    db_nonce.used = True
    session.add(db_nonce)

    user = session.get(User, db_nonce.user_id)
    if user:
        user.last_login = datetime.now(UTC)
        session.add(user)

    session.commit()

    # Generate JWT
    is_admin = is_admin_address(checksum_address)
    token_data = {
        "sub": checksum_address,
        "username": user.username if user else "Unknown",
        "is_admin": is_admin,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=JWT_EXPIRATION_MINUTES),
        "iss": "playlink-auth",
    }
    token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "token": token,
        "username": user.username if user else "Unknown",
        "is_admin": is_admin,
    }
