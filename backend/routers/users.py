"""Current-user profile endpoints (`/users/me`)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from config import DEFAULT_RATE_LIMIT
from dependencies import SessionDep, get_current_user_address
from models import User
from rate_limit import limiter
from schemas import UpdateUserRequest
from serializers import _user_payload
from usernames import validate_username

router = APIRouter(tags=["users"])


@router.get("/users/me")
@limiter.limit(DEFAULT_RATE_LIMIT)
def get_me(
    request: Request,  # noqa: ARG001
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_payload(user)


@router.patch("/users/me")
@limiter.limit(DEFAULT_RATE_LIMIT)
def update_me(
    request: Request,  # noqa: ARG001
    payload: UpdateUserRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    username = payload.username.strip()

    error = validate_username(username)
    if error == "invalid_format":
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-20 characters: letters, numbers, _ or -.",
        )
    if error == "profane":
        raise HTTPException(
            status_code=400, detail="Username contains inappropriate language."
        )

    if username == user.username:
        return _user_payload(user)

    existing = session.exec(select(User).where(User.username == username)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken.")

    user.username = username
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken.") from None
    session.refresh(user)
    return _user_payload(user)
