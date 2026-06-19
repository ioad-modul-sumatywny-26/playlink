"""WebSocket connection managers and their shared singletons.

``manager`` tracks listeners on the global active-rooms feed; ``chat_manager``
tracks per-room chat sockets. Both are module-level singletons imported by the
routers and the background cleanup task.
"""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(data)
            except Exception:
                # A stale global-list listener must not turn an already
                # committed room mutation into an HTTP 500 response.
                self.disconnect(connection)


class RoomChatManager:
    def __init__(self):
        self.rooms: dict[str, dict[WebSocket, str]] = {}

    async def connect(self, room: str, websocket: WebSocket, address: str):
        await websocket.accept()
        self.rooms.setdefault(room, {})[websocket] = address

    def disconnect(self, room: str, websocket: WebSocket):
        if room in self.rooms and websocket in self.rooms[room]:
            del self.rooms[room][websocket]
            if not self.rooms[room]:
                del self.rooms[room]

    async def broadcast(self, room: str, payload: str):
        for connection in list(self.rooms.get(room, {})):
            try:
                await connection.send_text(payload)
            except Exception:
                # Browsers can disappear without completing a close handshake.
                # Drop that socket and continue updating the remaining room.
                self.disconnect(room, connection)

    async def disconnect_user(self, room: str, address: str, code: int = 4409):
        """Close every room-chat connection authenticated as ``address``."""
        connections = self.rooms.get(room, {})
        targets = [
            websocket
            for websocket, connected_address in connections.items()
            if connected_address.lower() == address.lower()
        ]
        for websocket in targets:
            try:
                await websocket.close(code=code)
            except RuntimeError:
                # The browser may have closed between the broadcast and this
                # targeted cleanup. Its registry entry still needs removing.
                pass
            finally:
                self.disconnect(room, websocket)


manager = ConnectionManager()
chat_manager = RoomChatManager()
