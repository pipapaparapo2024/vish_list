from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, slug: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[slug].append(websocket)

    def disconnect(self, slug: str, websocket: WebSocket) -> None:
        if slug not in self.connections:
            return
        if websocket in self.connections[slug]:
            self.connections[slug].remove(websocket)
        if not self.connections[slug]:
            del self.connections[slug]

    async def broadcast(self, slug: str, message: dict[str, Any]) -> None:
        if slug not in self.connections:
            return
        dead: list[WebSocket] = []
        for connection in list(self.connections[slug]):
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead.append(connection)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(slug, connection)


manager = ConnectionManager()
