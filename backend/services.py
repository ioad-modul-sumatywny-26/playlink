"""Domain services: game seeding, room teardown and the cleanup task."""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from config import DEFAULT_GAMES, ROOM_CLEANUP_INTERVAL_SECONDS
from database import engine
from models import Game, Message, Room, RoomEvent, RoomEventRsvp
from serializers import get_rooms_payload
from ws.managers import manager

logger = logging.getLogger(__name__)


def _ensure_game(session: Session, name: str) -> Game:
    game = session.exec(select(Game).where(Game.name == name)).first()
    if game is not None:
        return game

    next_order = 1 + max(
        (g.sort_order for g in session.exec(select(Game)).all()), default=0
    )
    game = Game(name=name, sort_order=next_order)
    session.add(game)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(select(Game).where(Game.name == name)).first()
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="Game already exists") from None
    session.refresh(game)
    return game


def _purge_room(session: Session, room: Room) -> None:
    messages = session.exec(select(Message).where(Message.room_id == room.id)).all()
    for m in messages:
        session.delete(m)

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is not None:
        rsvps = session.exec(
            select(RoomEventRsvp).where(RoomEventRsvp.event_id == event.id)
        ).all()
        for r in rsvps:
            session.delete(r)
        session.delete(event)

    room.members.clear()
    session.delete(room)


def seed_default_games() -> None:
    with Session(engine) as session:
        existing = {g.name for g in session.exec(select(Game)).all()}
        next_order = 1 + max(
            (g.sort_order for g in session.exec(select(Game)).all()), default=0
        )
        added = False
        for name in DEFAULT_GAMES:
            if name in existing:
                continue
            session.add(Game(name=name, sort_order=next_order))
            next_order += 1
            added = True
        if added:
            session.commit()


async def cleanup_expired_rooms_task() -> None:
    """Periodically clean up expired rooms from the database."""
    while True:
        try:
            await asyncio.sleep(ROOM_CLEANUP_INTERVAL_SECONDS)

            with Session(engine) as session:
                now = datetime.now(UTC)
                expired_rooms = session.exec(
                    select(Room).where(Room.expires_at <= now)
                ).all()

                total_messages_deleted = 0
                for er in expired_rooms:
                    old_messages = session.exec(
                        select(Message).where(Message.room_id == er.id)
                    ).all()
                    total_messages_deleted += len(old_messages)
                    for m in old_messages:
                        session.delete(m)
                    old_event = session.exec(
                        select(RoomEvent).where(RoomEvent.room_id == er.id)
                    ).first()
                    if old_event is not None:
                        old_rsvps = session.exec(
                            select(RoomEventRsvp).where(
                                RoomEventRsvp.event_id == old_event.id
                            )
                        ).all()
                        for r in old_rsvps:
                            session.delete(r)
                        session.delete(old_event)
                    session.delete(er)

                if expired_rooms:
                    session.commit()
                    rooms_count = len(expired_rooms)
                    logger.info(
                        f"""Cleanup task deleted {rooms_count} room(s)
                        and {total_messages_deleted} message(s)"""
                    )

                    # Broadcast updated rooms payload to all WebSocket clients
                    rooms_payload = get_rooms_payload(session)
                    await manager.broadcast(rooms_payload)
        except Exception as exc:
            logger.exception(f"Error in cleanup_expired_rooms_task: {exc}")
