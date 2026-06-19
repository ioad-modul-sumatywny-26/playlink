"""WebSocket endpoints: the global rooms feed and per-room chat."""

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import select

from config import MAX_MSGS, SYSTEM_SENDER_ADDRESS, WINDOW, WS_LIMITS
from dependencies import SessionDep
from models import Message, Room, RoomMember, User
from security import _decode_jwt, _verify_chat_signature
from serializers import _msg_dict, get_rooms_payload
from ws.managers import chat_manager, manager

router = APIRouter()


@router.websocket("/ws/rooms")
async def websocket_rooms(websocket: WebSocket, session: SessionDep):
    await manager.connect(websocket)
    try:
        await websocket.send_text(get_rooms_payload(session))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/rooms/{room_name}/chat")
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

    await chat_manager.connect(room_name, websocket, address)
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
            if addr == SYSTEM_SENDER_ADDRESS:
                return "System"
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

            # Membership may have changed after the socket was accepted. Query
            # the link table directly so a stale relationship cache cannot let
            # a removed member continue writing to chat.
            membership = session.exec(
                select(RoomMember).where(
                    RoomMember.room_id == room.id,
                    RoomMember.user_id == user.id,
                )
            ).first()
            if membership is None:
                await websocket.close(code=4403)
                return

            now = time.time()

            key = address

            WS_LIMITS[key] = [t for t in WS_LIMITS[key] if now - t < WINDOW]

            if len(WS_LIMITS[key]) >= MAX_MSGS:
                await websocket.close(code=4429)
                return

            WS_LIMITS[key].append(now)

            try:
                data = json.loads(raw)
                content = str(data.get("content", "")).strip()
            except ValueError, TypeError:
                continue
            if not content or len(content) > 1000:
                continue

            # Issue #59: when a signature is supplied it must verify against the
            # connected identity, otherwise the message is rejected outright
            # (never stored or broadcast). A missing signature is a legacy /
            # no-key client and is accepted as unverified.
            raw_signature = data.get("signature")
            signature: str | None = None
            sent_at: str | None = None
            if raw_signature:
                signature = str(raw_signature)
                sent_at = str(data.get("sent_at", ""))
                if not _verify_chat_signature(
                    room_name, content, sent_at, signature, address
                ):
                    await websocket.send_text(
                        json.dumps({"type": "error", "detail": "signature_invalid"})
                    )
                    continue

            msg = Message(
                room_id=room.id,
                sender_address=address,
                content=content,
                signature=signature,
                sent_at=sent_at,
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
