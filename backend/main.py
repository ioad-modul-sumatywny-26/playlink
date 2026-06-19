"""Application entry point: wires middleware, lifespan and routers together.

The backend is split into focused modules:

* ``config``        — env parsing and static constants
* ``schemas``       — Pydantic request bodies
* ``dependencies``  — DB session + identity/admin auth dependencies
* ``security``      — nonce hashing, JWT decoding, chat-signature verification
* ``serializers``   — JSON payload builders shared by REST + WebSockets
* ``services``      — game seeding, room teardown, background cleanup
* ``ws.managers``   — WebSocket connection managers
* ``routers.*``     — the HTTP/WebSocket endpoints, grouped by domain

This module only assembles them.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler

# ``DEFAULT_RATE_LIMIT`` is used below by ``read_root``; the remaining names are
# backward-compatible re-exports. The test-suite reaches into ``main`` as a
# white-box facade (``main.X``), including in-place mutation of
# ``ADMIN_ADDRESSES`` — re-exporting the same objects keeps those references
# resolving after the split. See ``__all__`` for the full re-exported surface.
from config import (  # noqa: F401
    ADMIN_ADDRESSES,
    DEFAULT_RATE_LIMIT,
    SYSTEM_SENDER_ADDRESS,
    _parse_admin_addresses,
    is_admin_address,
)
from database import get_session
from rate_limit import limiter
from routers import auth, chat, events, games, rooms, users
from security import hash_nonce  # noqa: F401
from serializers import (  # noqa: F401
    _iso,
    _members_payload,
    _msg_dict,
    get_rooms_payload,
)
from services import cleanup_expired_rooms_task, seed_default_games
from ws.managers import (  # noqa: F401
    ConnectionManager,
    RoomChatManager,
    chat_manager,
    manager,
)

__all__ = [
    "ADMIN_ADDRESSES",
    "ConnectionManager",
    "RoomChatManager",
    "SYSTEM_SENDER_ADDRESS",
    "_iso",
    "_members_payload",
    "_msg_dict",
    "_parse_admin_addresses",
    "app",
    "chat_manager",
    "get_rooms_payload",
    "get_session",
    "hash_nonce",
    "is_admin_address",
    "manager",
]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_default_games()
    cleanup_task = asyncio.create_task(cleanup_expired_rooms_task())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Room cleanup task cancelled during shutdown")


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    "https://playlink.bartek.monster",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@limiter.limit(DEFAULT_RATE_LIMIT)
def read_root(request: Request):  # noqa: ARG001
    return {"status": "ok", "service": "playlink-auth"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(games.router)
app.include_router(events.router)
app.include_router(chat.router)
