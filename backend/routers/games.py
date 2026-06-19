"""Game catalog endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from config import DEFAULT_RATE_LIMIT
from dependencies import SessionDep, get_admin_address
from models import Game, Room
from rate_limit import limiter
from schemas import CreateGameRequest
from serializers import get_rooms_payload
from services import _purge_room
from ws.managers import chat_manager, manager

router = APIRouter(tags=["games"])


@router.get("/games")
@limiter.limit(DEFAULT_RATE_LIMIT)
def list_games(request: Request, session: SessionDep):  # noqa: ARG001
    games = session.exec(select(Game).order_by(Game.sort_order)).all()
    return [game.name for game in games]


@router.post("/games", status_code=201, dependencies=[Depends(get_admin_address)])
@limiter.limit(DEFAULT_RATE_LIMIT)
async def create_game(
    request: Request,  # noqa: ARG001
    body: CreateGameRequest,
    session: SessionDep,
):
    """Admin-only: add a new game category at the end of the sort order."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Game name is required")

    existing = session.exec(select(Game).where(Game.name == name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Game already exists")

    next_order = 1 + max(
        (g.sort_order for g in session.exec(select(Game)).all()), default=0
    )
    game = Game(name=name, sort_order=next_order)
    session.add(game)
    session.commit()
    session.refresh(game)
    return {"name": game.name, "sort_order": game.sort_order}


@router.delete(
    "/games/{name}", status_code=200, dependencies=[Depends(get_admin_address)]
)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def delete_game(
    request: Request,  # noqa: ARG001
    name: str,
    session: SessionDep,
    force: bool = False,
):
    """Admin-only: delete a game category.

    If rooms are still playing this game the request is refused with `409`
    unless `force=true`, in which case those rooms are closed first (cascading
    like `DELETE /rooms/{name}`) and their chat clients are redirected out.
    """
    game = session.exec(select(Game).where(Game.name == name)).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    rooms = session.exec(select(Room).where(Room.game == name)).all()
    if rooms and not force:
        raise HTTPException(
            status_code=409,
            detail=f"There are {len(rooms)} active rooms currently playing this game.",
        )

    closed_rooms = [room.name for room in rooms]
    for room in rooms:
        _purge_room(session, room)
    session.delete(game)
    session.commit()

    for closed_name in closed_rooms:
        await chat_manager.broadcast(
            closed_name, json.dumps({"type": "room_closed", "room": closed_name})
        )
    if closed_rooms:
        await manager.broadcast(get_rooms_payload(session))
    return {"status": "deleted", "game": name, "rooms_closed": closed_rooms}
