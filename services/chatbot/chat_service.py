from __future__ import annotations

from schemas.chatbot_schema import ChatRequest, ChatResponse, ChatToolCall, PendingActionResponse
from services.chatbot.agent import ChatAgent
from services.chatbot.context import conversation_store
from services.chatbot.tool_executor import ToolExecutor
from utils.exceptions import AppException
from utils.logger import logger


class ChatService:
    def __init__(self) -> None:
        self.agent = ChatAgent()
        self.executor = ToolExecutor(conversation_store)

    async def handle_chat(self, request: ChatRequest, db, current_user: dict) -> ChatResponse:
        conversation_id, state = conversation_store.get(request.conversation_id)
        state.last_context = request.context

        if request.confirmation_token:
            result = await self.executor.execute_confirmed(
                request.confirmation_token,
                db,
                current_user,
                request.context,
                state,
            )
            response_message = self._message_for_result(result)
            conversation_store.add_message(state, "user", request.message)
            conversation_store.add_message(state, "assistant", response_message)
            return ChatResponse(
                message=response_message,
                conversation_id=conversation_id,
                tool_calls=[ChatToolCall(tool=result.tool, status="success" if result.success else "error", result=result.model_dump())],
                map_events=[result.map_event] if result.map_event else [],
            )

        plan = await self.agent.plan(request.message, state.messages, request.context)
        conversation_store.add_message(state, "user", request.message)

        tool_calls: list[ChatToolCall] = []
        map_events: list[dict] = []
        pending_response = None
        messages: list[str] = []

        for planned in plan.get("tool_calls") or []:
            tool_name = planned.get("tool")
            arguments = planned.get("arguments") or {}
            if not tool_name:
                continue
            try:
                result, pending = await self.executor.execute(
                    tool_name,
                    arguments,
                    db,
                    current_user,
                    request.context,
                    state,
                )
            except AppException as exc:
                tool_calls.append(ChatToolCall(
                    tool=tool_name,
                    status="error",
                    arguments=arguments,
                    error={"code": type(exc).__name__, "message": exc.detail},
                ))
                messages.append(exc.detail)
                continue

            if pending is not None:
                pending_response = PendingActionResponse(**pending)
                tool_calls.append(ChatToolCall(
                    tool=tool_name,
                    status="pending_confirmation",
                    arguments=arguments,
                ))
                messages.append(pending["message"])
                continue

            if result is None:
                continue
            status = "success" if result.success else "clarification_required" if result.error and result.error.get("code") == "CLARIFICATION_REQUIRED" else "error"
            tool_calls.append(ChatToolCall(
                tool=result.tool,
                status=status,
                arguments=arguments,
                result=result.model_dump() if result.success else None,
                error=result.error,
            ))
            if result.map_event:
                map_events.append(result.map_event)
            messages.append(self._message_for_result(result))

        message = " ".join(messages).strip() or plan.get("message") or "Done."
        conversation_store.add_message(state, "assistant", message)
        logger.info(
            "Chat request completed | user_id=%s | conversation_id=%s | tools=%s",
            current_user.get("user_id"),
            conversation_id,
            [call.tool for call in tool_calls],
        )
        return ChatResponse(
            message=message,
            conversation_id=conversation_id,
            tool_calls=tool_calls,
            map_events=map_events,
            pending_action=pending_response,
        )

    def _message_for_result(self, result) -> str:
        if not result.success:
            return result.error.get("message", "The tool could not complete.") if result.error else "The tool could not complete."
        if "count" in result.data:
            return f"{result.tool} completed. Found {result.data['count']} item(s)."
        return f"{result.tool} completed successfully."
