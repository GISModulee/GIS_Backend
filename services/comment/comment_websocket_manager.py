import asyncio
from collections import defaultdict
from typing import Any
 
from fastapi import WebSocket
 
from utils.logger import logger
 
 
class CommentConnectionManager:
    """Manage authenticated WebSocket subscribers grouped by (case_id, feature_number)."""
 
    def __init__(self) -> None:
        self._connections: dict[tuple[int, int], set[WebSocket]] = defaultdict(set)
 
    async def connect(self, case_id: int, feature_number: int, websocket: WebSocket) -> None:
        key = (case_id, feature_number)
        await websocket.accept()
        self._connections[key].add(websocket)
        logger.info(
            "Comment WebSocket connected | case_id=%s | feature_number=%s | subscribers=%s",
            case_id,
            feature_number,
            len(self._connections[key]),
        )
 
    async def disconnect(self, case_id: int, feature_number: int, websocket: WebSocket) -> None:
        key = (case_id, feature_number)
        connections = self._connections.get(key)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(key, None)
        logger.info(
            "Comment WebSocket disconnected | case_id=%s | feature_number=%s | subscribers=%s",
            case_id,
            feature_number,
            len(self._connections.get(key, ())),
        )
 
    async def broadcast(self, case_id: int, feature_number: int, message: dict[str, Any]) -> None:
        key = (case_id, feature_number)
        connections = tuple(self._connections.get(key, ()))
        if not connections:
            return
 
        deliveries = await asyncio.gather(
            *(connection.send_json(message) for connection in connections),
            return_exceptions=True,
        )
        for connection, result in zip(connections, deliveries):
            if isinstance(result, Exception):
                logger.warning(
                    "Comment WebSocket delivery failed | case_id=%s | feature_number=%s | error=%s",
                    case_id,
                    feature_number,
                    type(result).__name__,
                )
                await self.disconnect(case_id, feature_number, connection)
 
 
comment_connection_manager = CommentConnectionManager()
