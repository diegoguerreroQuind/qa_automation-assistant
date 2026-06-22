import json
import asyncio
from fastapi import WebSocket


class WebSocketManager:
    """Manages active WebSocket connections per execution_id."""

    def __init__(self):
        # execution_id → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, execution_id: str, ws: WebSocket) -> None:
        await ws.accept()
        if execution_id not in self._connections:
            self._connections[execution_id] = set()
        self._connections[execution_id].add(ws)

    def disconnect(self, execution_id: str, ws: WebSocket) -> None:
        if execution_id in self._connections:
            self._connections[execution_id].discard(ws)
            if not self._connections[execution_id]:
                del self._connections[execution_id]

    async def broadcast(self, execution_id: str, message: dict) -> None:
        """Send message to all clients listening to this execution."""
        connections = self._connections.get(execution_id, set()).copy()
        dead: set[WebSocket] = set()
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(execution_id, ws)


ws_manager = WebSocketManager()
