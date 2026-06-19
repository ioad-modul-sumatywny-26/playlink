"""Reusable FastAPI dependencies: DB session and identity resolution."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from config import is_admin_address
from database import get_session
from security import _decode_jwt

SessionDep = Annotated[Session, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify", auto_error=False)


async def get_current_user_address(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return _decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError, KeyError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


async def get_admin_address(
    address: Annotated[str, Depends(get_current_user_address)],
) -> str:
    """Authorize the caller as an administrator.

    Reuses the normal JWT auth to resolve the identity address, then checks it
    against the `ADMIN_ADDRESSES` whitelist. The whitelist is authoritative —
    a forged `is_admin` JWT claim cannot grant access here.
    """
    if not is_admin_address(address):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return address
