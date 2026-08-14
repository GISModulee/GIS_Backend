import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from utils.logger import logger


class LayerConnectionManager:
    """Manage authenticated WebSocket subscribers grouped by case_id."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, case_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[case_id].add(websocket)
        logger.info(
            "Layer WebSocket connected | case_id=%s | subscribers=%s",
            case_id,
            len(self._connections[case_id]),
        )

    def disconnect(self, case_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(case_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(case_id, None)
        logger.info(
            "Layer WebSocket disconnected | case_id=%s | subscribers=%s",
            case_id,
            len(self._connections.get(case_id, ())),
        )

    async def broadcast(self, case_id: int, message: dict[str, Any]) -> None:
        connections = tuple(self._connections.get(case_id, ()))
        if not connections:
            return

        deliveries = await asyncio.gather(
            *(connection.send_json(message) for connection in connections),
            return_exceptions=True,
        )
        for connection, result in zip(connections, deliveries):
            if isinstance(result, Exception):
                logger.warning(
                    "Layer WebSocket delivery failed | case_id=%s | error=%s",
                    case_id,
                    type(result).__name__,
                )
                self.disconnect(case_id, connection)


layer_connection_manager = LayerConnectionManager()