import asyncio
import logging
from typing import Any
from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for real-time safety alert broadcasts."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total active: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcasts a JSON message asynchronously to all connected clients."""
        if not self.active_connections:
            return

        stale_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending message over WebSocket: {e}")
                stale_connections.append(connection)

        for stale in stale_connections:
            self.disconnect(stale)

    def broadcast_sync(self, message: dict[str, Any]) -> None:
        """Synchronously triggers broadcast from synchronous routes and services."""
        if not self.active_connections:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.create_task(self.broadcast(message))
        else:
            try:
                asyncio.run(self.broadcast(message))
            except Exception as e:
                logger.warning(f"Failed to broadcast_sync: {e}")


ws_manager = ConnectionManager()
