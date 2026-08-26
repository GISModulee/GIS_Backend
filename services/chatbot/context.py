from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from schemas.chatbot_schema import ChatContext
from utils.config import settings


class ConversationState:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.last_context: ChatContext | None = None
        self.pending_actions: dict[str, dict] = {}


class ConversationStore:
    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}

    def get(self, conversation_id: str | None) -> tuple[str, ConversationState]:
        actual_id = conversation_id or str(uuid4())
        if actual_id not in self._states:
            self._states[actual_id] = ConversationState()
        return actual_id, self._states[actual_id]

    def add_message(self, state: ConversationState, role: str, content: str) -> None:
        state.messages.append({"role": role, "content": content})
        if len(state.messages) > settings.CHAT_HISTORY_LIMIT:
            del state.messages[:-settings.CHAT_HISTORY_LIMIT]

    def create_pending_action(self, state: ConversationState, tool: str, arguments: dict, message: str) -> dict:
        token = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.CHAT_PENDING_ACTION_TTL_SECONDS
        )
        pending = {
            "token": token,
            "tool": tool,
            "arguments": arguments,
            "expires_at": expires_at,
            "message": message,
        }
        state.pending_actions[token] = pending
        return pending

    def pop_pending_action(self, state: ConversationState, token: str) -> dict | None:
        pending = state.pending_actions.pop(token, None)
        if pending is None:
            return None
        if pending["expires_at"] < datetime.now(timezone.utc):
            return None
        return pending


conversation_store = ConversationStore()
