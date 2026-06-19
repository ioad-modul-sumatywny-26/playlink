"""Cryptographic helpers: nonce hashing, JWT decoding and chat signatures."""

import hashlib
from datetime import UTC, datetime

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct

from config import CHAT_SIGNATURE_SKEW_SECONDS, JWT_ALGORITHM, JWT_SECRET


def hash_nonce(nonce_value: str) -> str:
    return hashlib.sha256(nonce_value.encode()).hexdigest()


def _decode_jwt(token: str) -> str:
    """Decode a JWT and return its `sub` claim. Raises on any failure."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    address = payload.get("sub")
    if not isinstance(address, str):
        raise jwt.InvalidTokenError("Missing sub claim")
    return address


def _chat_signing_message(room_name: str, content: str, sent_at: str) -> str:
    """Canonical text the client signs and the server reconstructs.

    Must stay byte-for-byte in sync with the frontend builder in
    ``frontend/src/lib/signing.ts``.
    """
    return (
        "PlayLink signed chat message\n"
        f"room={room_name}\n"
        f"sent_at={sent_at}\n"
        f"content={content}"
    )


def _verify_chat_signature(
    room_name: str, content: str, sent_at: str, signature: str, address: str
) -> bool:
    """True iff ``signature`` was produced by ``address`` over the canonical
    payload and ``sent_at`` is within the allowed clock skew."""
    try:
        signed_at = datetime.fromisoformat(sent_at)
    except ValueError, TypeError:
        return False
    if signed_at.tzinfo is None:
        signed_at = signed_at.replace(tzinfo=UTC)
    drift = abs((datetime.now(UTC) - signed_at).total_seconds())
    if drift > CHAT_SIGNATURE_SKEW_SECONDS:
        return False

    message = encode_defunct(text=_chat_signing_message(room_name, content, sent_at))
    try:
        recovered = Account.recover_message(message, signature=signature)
    except Exception:
        return False
    return recovered.lower() == address.lower()
