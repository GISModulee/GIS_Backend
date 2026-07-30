import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from utils.logger import logger


class CommentConnectionManager:
    """Manage authenticated WebSocket subscribers grouped by feature."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, feature_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[feature_id].add(websocket)
        logger.info(
            "Comment WebSocket connected | feature_id=%s | subscribers=%s",
            feature_id,
            len(self._connections[feature_id]),
        )

    def disconnect(self, feature_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(feature_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(feature_id, None)
        logger.info(
            "Comment WebSocket disconnected | feature_id=%s | subscribers=%s",
            feature_id,
            len(self._connections.get(feature_id, ())),
        )

    async def broadcast(self, feature_id: int, message: dict[str, Any]) -> None:
        connections = tuple(self._connections.get(feature_id, ()))
        if not connections:
            return

        deliveries = await asyncio.gather(
            *(connection.send_json(message) for connection in connections),
            return_exceptions=True,
        )
        for connection, result in zip(connections, deliveries):
            if isinstance(result, Exception):
                logger.warning(
                    "Comment WebSocket delivery failed | feature_id=%s | error=%s",
                    feature_id,
                    type(result).__name__,
                )
                self.disconnect(feature_id, connection)


comment_connection_manager = CommentConnectionManager()
