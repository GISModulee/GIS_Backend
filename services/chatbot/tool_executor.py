from __future__ import annotations

from pydantic import ValidationError

from services.chatbot.context import ConversationState, ConversationStore
from services.chatbot.permissions import ensure_tool_permission
from services.chatbot.schemas import ToolResult
from services.chatbot.tool_registry import TOOL_REGISTRY
from utils.exceptions import AppException, BadRequestError
from utils.logger import logger


class ToolExecutor:
    def __init__(self, store: ConversationStore) -> None:
        self.store = store

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        db,
        current_user: dict,
        context,
        state: ConversationState,
        confirmed: bool = False,
    ) -> tuple[ToolResult | None, dict | None]:
        tool = TOOL_REGISTRY.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                tool=tool_name,
                error={"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"},
            ), None

        try:
            typed_args = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult(
                success=False,
                tool=tool_name,
                error={"code": "TOOL_VALIDATION_ERROR", "message": "Invalid tool arguments.", "details": exc.errors()},
            ), None

        ensure_tool_permission(current_user, tool.permission)

        if tool.confirmation_required and not confirmed:
            pending = self.store.create_pending_action(
                state,
                tool_name,
                typed_args.model_dump(exclude_none=True),
                f"Please confirm before I run {tool_name}.",
            )
            return None, pending

        logger.info(
            "Executing chatbot tool | user_id=%s | role=%s | tool=%s",
            current_user.get("user_id"),
            current_user.get("role"),
            tool_name,
        )
        return await tool.handler(typed_args, db, current_user, context), None

    async def execute_confirmed(
        self,
        token: str,
        db,
        current_user: dict,
        context,
        state: ConversationState,
    ) -> ToolResult:
        pending = self.store.pop_pending_action(state, token)
        if pending is None:
            raise BadRequestError("Confirmation expired or not found.")
        result, _ = await self.execute(
            pending["tool"],
            pending["arguments"],
            db,
            current_user,
            context,
            state,
            confirmed=True,
        )
        if result is None:
            raise BadRequestError("Confirmed action could not be executed.")
        return result
