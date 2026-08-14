import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from utils.logger import logger


class CursorConnectionManager:
    """Manage authenticated WebSocket subscribers grouped by case_id,
    tracking which user owns each connection for cursor broadcast/label."""

    def __init__(self) -> None:
        # case_id -> { websocket: user_info_dict }
        self._connections: dict[int, dict[WebSocket, dict]] = defaultdict(dict)

    async def connect(self, case_id: int, websocket: WebSocket, user_info: dict) -> None:
        await websocket.accept()
        self._connections[case_id][websocket] = user_info
        logger.info(
            "Cursor WebSocket connected | case_id=%s | user_id=%s | subscribers=%s",
            case_id,
            user_info.get("user_id"),
            len(self._connections[case_id]),
        )

    def disconnect(self, case_id: int, websocket: WebSocket) -> dict | None:
        connections = self._connections.get(case_id)
        if not connections:
            return None
        user_info = connections.pop(websocket, None)
        if not connections:
            self._connections.pop(case_id, None)
        logger.info(
            "Cursor WebSocket disconnected | case_id=%s | user_id=%s | subscribers=%s",
            case_id,
            user_info.get("user_id") if user_info else None,
            len(self._connections.get(case_id, {})),
        )
        return user_info

    async def broadcast_except(self, case_id: int, sender: WebSocket, message: dict[str, Any]) -> None:
        connections = self._connections.get(case_id, {})
        targets = tuple(ws for ws in connections if ws is not sender)
        if not targets:
            return

        deliveries = await asyncio.gather(
            *(ws.send_json(message) for ws in targets),
            return_exceptions=True,
        )
        for ws, result in zip(targets, deliveries):
            if isinstance(result, Exception):
                logger.warning(
                    "Cursor WebSocket delivery failed | case_id=%s | error=%s",
                    case_id,
                    type(result).__name__,
                )
                self.disconnect(case_id, ws)

    async def broadcast_to_all(self, case_id: int, message: dict[str, Any]) -> None:
        connections = tuple(self._connections.get(case_id, {}).keys())
        if not connections:
            return

        deliveries = await asyncio.gather(
            *(ws.send_json(message) for ws in connections),
            return_exceptions=True,
        )
        for ws, result in zip(connections, deliveries):
            if isinstance(result, Exception):
                self.disconnect(case_id, ws)


cursor_connection_manager = CursorConnectionManager()