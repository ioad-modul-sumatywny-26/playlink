import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, HttpUrl
from pydantic import Field as PydField
from sqlmodel import Session, select

from database import get_session
from models import (
    Game,
    Message,
    Nonce,
    Room,
    RoomEvent,
    RoomEventRsvp,
    RsvpStatus,
    User,
)

# Load .env from project root if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
NONCE_EXPIRATION_MINUTES = int(os.getenv("NONCE_EXPIRATION_MINUTES", "5"))
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))


# --- Schemas ---
class VerifyRequest(BaseModel):
    address: str
    nonce: str
    signature: str


class CreateRoomRequest(BaseModel):
    name: str
    game: str
    players_max: int
    description: str | None = PydField(default=None, max_length=500)
    communicator_link: HttpUrl | None = None
    requirements: str | None = PydField(default=None, max_length=1000)


class ScheduleEventRequest(BaseModel):
    """Body for `PUT /rooms/{name}/event`. Both timestamps must be in the future."""

    starts_at: datetime
    ends_at: datetime


class SetRsvpRequest(BaseModel):
    """Body for `PUT /rooms/{name}/event/rsvp`."""

    status: RsvpStatus


# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: str):
        for connection in self.active_connections:
            await connection.send_text(data)


manager = ConnectionManager()


class RoomChatManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room, []).append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        if room in self.rooms and websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)
            if not self.rooms[room]:
                del self.rooms[room]

    async def broadcast(self, room: str, payload: str):
        for connection in list(self.rooms.get(room, [])):
            await connection.send_text(payload)


chat_manager = RoomChatManager()


# --- Helpers ---
def hash_nonce(nonce_value: str) -> str:
    return hashlib.sha256(nonce_value.encode()).hexdigest()


def get_rooms_payload(session: Session) -> str:
    now = datetime.now(UTC)

    # Optional cleanup of expired rooms before returning the payload.
    # NOTE: The DB layer also has ON DELETE CASCADE on RoomEvent / RoomEventRsvp
    # / Message, but we delete explicitly so the same code path works on
    # SQLite (test environment) where FK cascades depend on PRAGMA settings.
    expired_rooms = session.exec(select(Room).where(Room.expires_at <= now)).all()
    for er in expired_rooms:
        old_messages = session.exec(
            select(Message).where(Message.room_id == er.id)
        ).all()
        for m in old_messages:
            session.delete(m)
        old_event = session.exec(
            select(RoomEvent).where(RoomEvent.room_id == er.id)
        ).first()
        if old_event is not None:
            old_rsvps = session.exec(
                select(RoomEventRsvp).where(RoomEventRsvp.event_id == old_event.id)
            ).all()
            for r in old_rsvps:
                session.delete(r)
            session.delete(old_event)
        session.delete(er)
    if expired_rooms:
        session.commit()

    return json.dumps(
        [
            {
                "name": r.name,
                "game": r.game,
                "players_active": len(r.members),
                "players_max": r.players_max,
                "member_addresses": [m.identity_address for m in r.members],
                "description": r.description,
                "communicator_link": r.communicator_link,
                "requirements": r.requirements,
                "expires_at": _iso(r.expires_at),
            }
            for r in session.exec(select(Room)).all()
        ]
    )


SessionDep = Annotated[Session, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify", auto_error=False)


def _decode_jwt(token: str) -> str:
    """Decode a JWT and return its `sub` claim. Raises on any failure."""
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    address = payload.get("sub")
    if not isinstance(address, str):
        raise jwt.InvalidTokenError("Missing sub claim")
    return address


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


def _iso(dt: datetime) -> str:
    """Serialize a datetime to ISO 8601, appending `Z` for naive UTC values."""
    return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()


def _members_payload(room: Room) -> list[dict[str, str]]:
    """Compact roster for chat WS `roster_update` frames."""
    return [
        {"address": m.identity_address, "username": m.username} for m in room.members
    ]


def _serialize_event_state(session: Session, room: Room) -> dict | None:
    """Build the JSON payload for a room's scheduled event.

    Returns `None` when the room has no event yet. Used by both the REST
    endpoints and the chat WebSocket so that `event_update` frames stay
    in sync with `GET /rooms/{name}/event`.
    """
    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        return None

    rsvp_rows = session.exec(
        select(RoomEventRsvp, User)
        .join(User, User.id == RoomEventRsvp.user_id)
        .where(RoomEventRsvp.event_id == event.id)
    ).all()

    return {
        "starts_at": _iso(event.starts_at),
        "ends_at": _iso(event.ends_at),
        "created_by": event.created_by,
        "created_at": _iso(event.created_at),
        "updated_at": _iso(event.updated_at),
        "rsvps": [
            {
                "address": user.identity_address,
                "username": user.username,
                "status": rsvp.status.value,
                "updated_at": _iso(rsvp.updated_at),
            }
            for rsvp, user in rsvp_rows
        ],
    }


DEFAULT_GAMES: list[str] = [
    "Quake III Arena",
    "Diablo II",
    "StarCraft",
    "Half-Life",
    "Unreal Tournament",
]


def seed_default_games() -> None:
    """Idempotent: insert any DEFAULT_GAMES rows that don't exist yet."""
    from database import engine

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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_default_games()
    yield


app = FastAPI(lifespan=lifespan)

# Configure CORS
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

# --- Endpoints ---


@app.get("/")
def read_root():
    return {"status": "ok", "service": "playlink-auth"}


@app.post("/auth/request-nonce")
def request_nonce(address: str, session: SessionDep):
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


@app.post("/auth/verify")
def verify_signature(body: VerifyRequest, session: SessionDep):
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
    token_data = {
        "sub": checksum_address,
        "username": user.username if user else "Unknown",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=JWT_EXPIRATION_MINUTES),
        "iss": "playlink-auth",
    }
    token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {"token": token, "username": user.username if user else "Unknown"}


@app.get("/users/me", response_model=User)
def get_me(
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/rooms")
def list_rooms(session: SessionDep):
    return session.exec(select(Room)).all()


@app.get("/rooms/{room_name}")
def get_room(room_name: str, session: SessionDep):
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "name": room.name,
        "game": room.game,
        "players_max": room.players_max,
        "players_active": len(room.members),
        "member_addresses": [m.identity_address for m in room.members],
        "members": [
            {"address": m.identity_address, "username": m.username}
            for m in room.members
        ],
        "description": room.description,
        "communicator_link": room.communicator_link,
        "requirements": room.requirements,
        "created_by": room.created_by,
        "expires_at": _iso(room.expires_at),
        "event": _serialize_event_state(session, room),
    }


@app.get("/games")
def list_games(session: SessionDep):
    games = session.exec(select(Game).order_by(Game.sort_order)).all()
    return [game.name for game in games]


@app.post("/rooms", status_code=201)
async def create_room(
    body: CreateRoomRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    now = datetime.now(UTC)

    # Clean up expired rooms for accurate counts
    expired_rooms = session.exec(select(Room).where(Room.expires_at <= now)).all()
    for er in expired_rooms:
        old_messages = session.exec(
            select(Message).where(Message.room_id == er.id)
        ).all()
        for m in old_messages:
            session.delete(m)
        session.delete(er)
    session.commit()

    existing = session.exec(select(Room).where(Room.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Room name already taken")

    user_rooms_count = len(
        session.exec(select(Room).where(Room.created_by == address)).all()
    )
    if user_rooms_count >= 3:
        raise HTTPException(
            status_code=400, detail="You can create a maximum of 3 rooms."
        )

    valid_game = session.exec(select(Game).where(Game.name == body.game)).first()
    if not valid_game:
        raise HTTPException(status_code=400, detail="Unsupported game")

    room = Room(
        name=body.name,
        game=body.game,
        players_max=body.players_max,
        description=body.description,
        communicator_link=(
            str(body.communicator_link) if body.communicator_link else None
        ),
        requirements=body.requirements,
        created_by=address,
    )

    # Auto-join creator
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if user:
        room.members.append(user)

    session.add(room)
    session.commit()
    session.refresh(room)

    await manager.broadcast(get_rooms_payload(session))
    return {"status": "created", "room": room.name}


@app.post("/rooms/{room_name}/join", status_code=200)
async def join_room(
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user in room.members:
        raise HTTPException(status_code=400, detail="You are already in this room")

    if len(room.members) >= room.players_max:
        raise HTTPException(status_code=400, detail="Room is full")

    room.members.append(user)
    session.add(room)
    session.commit()

    await manager.broadcast(get_rooms_payload(session))
    await chat_manager.broadcast(
        room_name,
        json.dumps({"type": "roster_update", "members": _members_payload(room)}),
    )
    return {"status": "joined", "room": room.name}


@app.post("/rooms/{room_name}/leave", status_code=200)
async def leave_room(
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in room.members:
        raise HTTPException(status_code=400, detail="You are not in this room")

    # Drop the leaving user's RSVP (if any) so an event's roster reflects
    # the current member set. Idempotent — runs even when no event exists.
    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    rsvp_to_drop: RoomEventRsvp | None = None
    if event is not None:
        rsvp_to_drop = session.exec(
            select(RoomEventRsvp).where(
                RoomEventRsvp.event_id == event.id,
                RoomEventRsvp.user_id == user.id,
            )
        ).first()
        if rsvp_to_drop is not None:
            session.delete(rsvp_to_drop)

    room.members.remove(user)
    session.add(room)
    session.commit()

    await manager.broadcast(get_rooms_payload(session))
    await chat_manager.broadcast(
        room_name,
        json.dumps({"type": "roster_update", "members": _members_payload(room)}),
    )
    if rsvp_to_drop is not None:
        await chat_manager.broadcast(
            room_name,
            json.dumps(
                {"type": "event_update", "event": _serialize_event_state(session, room)}
            ),
        )
    return {"status": "left", "room": room.name}


@app.get("/rooms/{room_name}/event")
def get_room_event(room_name: str, session: SessionDep):
    """Return the room's scheduled event (if any), including the RSVP roster.

    Mirrors `GET /rooms/{name}` in being public — anyone can browse the
    schedule, only members are allowed to RSVP.
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    event_state = _serialize_event_state(session, room)
    if event_state is None:
        raise HTTPException(status_code=404, detail="No event scheduled")
    return event_state


@app.put("/rooms/{room_name}/event", status_code=200)
async def schedule_room_event(
    room_name: str,
    body: ScheduleEventRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Create or replace the scheduled event for a room.

    Only the room creator may schedule. `starts_at` must lie in the future
    and `ends_at` must come after `starts_at`. The room's `expires_at` is
    automatically extended past `ends_at` so the room stays alive until the
    event finishes (plus a small grace period for stragglers).
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.created_by.lower() != address.lower():
        raise HTTPException(
            status_code=403, detail="Only the room creator can schedule an event"
        )

    starts_at = body.starts_at
    ends_at = body.ends_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    else:
        starts_at = starts_at.astimezone(UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)
    else:
        ends_at = ends_at.astimezone(UTC)

    now = datetime.now(UTC)
    if starts_at <= now:
        raise HTTPException(status_code=400, detail="starts_at must be in the future")
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="ends_at must be after starts_at")

    # Keep the room alive for the entire event plus a 30-minute grace period
    # so members don't get prune'd out mid-session.
    grace = timedelta(minutes=30)
    expires_at = room.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    new_expiry = max(expires_at, ends_at + grace)
    room_expiry_changed = new_expiry != expires_at
    if room_expiry_changed:
        room.expires_at = new_expiry
        session.add(room)

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        event = RoomEvent(
            room_id=room.id,
            starts_at=starts_at,
            ends_at=ends_at,
            created_by=address,
        )
        session.add(event)
    else:
        event.starts_at = starts_at
        event.ends_at = ends_at
        event.updated_at = datetime.now(UTC)
        session.add(event)
    session.commit()

    payload = _serialize_event_state(session, room)
    await chat_manager.broadcast(
        room_name, json.dumps({"type": "event_update", "event": payload})
    )
    if room_expiry_changed:
        await manager.broadcast(get_rooms_payload(session))
    return payload


@app.delete("/rooms/{room_name}/event", status_code=200)
async def cancel_room_event(
    room_name: str,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Delete the scheduled event for a room and clear all RSVPs."""
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.created_by.lower() != address.lower():
        raise HTTPException(
            status_code=403, detail="Only the room creator can cancel the event"
        )

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        raise HTTPException(status_code=404, detail="No event scheduled")

    rsvps = session.exec(
        select(RoomEventRsvp).where(RoomEventRsvp.event_id == event.id)
    ).all()
    for r in rsvps:
        session.delete(r)
    session.delete(event)
    session.commit()

    await chat_manager.broadcast(
        room_name, json.dumps({"type": "event_update", "event": None})
    )
    return {"status": "cancelled", "room": room.name}


@app.put("/rooms/{room_name}/event/rsvp", status_code=200)
async def set_room_event_rsvp(
    room_name: str,
    body: SetRsvpRequest,
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    """Upsert the caller's RSVP for the room's scheduled event.

    Only current members of the room may RSVP. The caller's status
    overwrites any previous one (one RSVP per user per event).
    """
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in room.members:
        raise HTTPException(
            status_code=403, detail="Only room members can RSVP to the event"
        )

    event = session.exec(select(RoomEvent).where(RoomEvent.room_id == room.id)).first()
    if event is None:
        raise HTTPException(status_code=404, detail="No event scheduled")

    rsvp = session.exec(
        select(RoomEventRsvp).where(
            RoomEventRsvp.event_id == event.id,
            RoomEventRsvp.user_id == user.id,
        )
    ).first()
    if rsvp is None:
        rsvp = RoomEventRsvp(
            event_id=event.id,
            user_id=user.id,
            status=body.status,
        )
        session.add(rsvp)
    else:
        rsvp.status = body.status
        rsvp.updated_at = datetime.now(UTC)
        session.add(rsvp)
    session.commit()
    session.refresh(rsvp)

    rsvp_payload = {
        "address": user.identity_address,
        "username": user.username,
        "status": rsvp.status.value,
        "updated_at": _iso(rsvp.updated_at),
    }
    await chat_manager.broadcast(
        room_name, json.dumps({"type": "rsvp_update", "rsvp": rsvp_payload})
    )
    return rsvp_payload


@app.websocket("/ws/rooms")
async def websocket_rooms(websocket: WebSocket, session: SessionDep):
    await manager.connect(websocket)
    try:
        await websocket.send_text(get_rooms_payload(session))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _msg_dict(msg: Message, sender_username: str) -> dict:
    return {
        "id": msg.id,
        "sender_address": msg.sender_address,
        "sender_username": sender_username,
        "content": msg.content,
        "created_at": _iso(msg.created_at),
    }


@app.websocket("/ws/rooms/{room_name}/chat")
async def websocket_chat(
    websocket: WebSocket,
    room_name: str,
    token: str,
    session: SessionDep,
):
    # 1. Authenticate via JWT in query param (browsers can't set WS headers).
    try:
        address = _decode_jwt(token)
    except Exception:
        await websocket.close(code=4401)
        return

    # 2. Room must exist.
    room = session.exec(select(Room).where(Room.name == room_name)).first()
    if not room:
        await websocket.close(code=4404)
        return

    # 3. Caller must be a member.
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user or user not in room.members:
        await websocket.close(code=4403)
        return

    await chat_manager.connect(room_name, websocket)
    try:
        # Send last 50 messages in chronological order.
        recent = session.exec(
            select(Message)
            .where(Message.room_id == room.id)
            .order_by(Message.created_at.desc())
            .limit(50)
        ).all()
        username_cache: dict[str, str] = {}

        def _username_for(addr: str) -> str:
            cached = username_cache.get(addr)
            if cached is not None:
                return cached
            sender = session.exec(
                select(User).where(User.identity_address == addr)
            ).first()
            name = sender.username if sender else addr
            username_cache[addr] = name
            return name

        history_payload = json.dumps(
            {
                "type": "history",
                "messages": [
                    _msg_dict(m, _username_for(m.sender_address))
                    for m in reversed(recent)
                ],
            }
        )
        await websocket.send_text(history_payload)

        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                content = str(data.get("content", "")).strip()
            except ValueError, TypeError:
                continue
            if not content or len(content) > 1000:
                continue

            msg = Message(
                room_id=room.id,
                sender_address=address,
                content=content,
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)

            await chat_manager.broadcast(
                room_name,
                json.dumps(
                    {"type": "message", "message": _msg_dict(msg, user.username)}
                ),
            )
    except WebSocketDisconnect:
        chat_manager.disconnect(room_name, websocket)
