from __future__ import annotations

import json
import re
from typing import Any

from schemas.chatbot_schema import ChatContext
from services.chatbot.ollama_client import OllamaClient
from services.chatbot.tool_registry import TOOL_REGISTRY
from utils.logger import logger


class ChatAgent:
    def __init__(self) -> None:
        self.ollama = OllamaClient()

    async def plan(self, message: str, history: list[dict[str, str]], context: ChatContext) -> dict[str, Any]:
        messages = [
            *history,
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "message": message,
                        "context": context.model_dump(exclude_none=True),
                    }
                ),
            },
        ]
        response = await self.ollama.chat(messages, TOOL_REGISTRY.ollama_schemas())
        parsed = self._parse_ollama_response(response)
        if parsed.get("tool_calls") or parsed.get("message"):
            return parsed
        logger.info("Ollama returned an empty structured plan; using deterministic read-only planner")
        return self._fallback_plan(message, context)

    def _parse_ollama_response(self, response: dict[str, Any]) -> dict[str, Any]:
        message = response.get("message") or {}
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            tool_calls.append({
                "tool": function.get("name"),
                "arguments": function.get("arguments") or {},
            })
        if tool_calls:
            return {"message": "", "tool_calls": tool_calls, "clarification_required": False}

        content = message.get("content") or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"message": content, "tool_calls": [], "clarification_required": False}
        parsed.setdefault("tool_calls", [])
        parsed.setdefault("message", "")
        return parsed

    def _fallback_plan(self, message: str, context: ChatContext) -> dict[str, Any]:
        text = message.lower()
        numbers = [int(value) for value in re.findall(r"\b\d+\b", text)]

        if "layer" in text and ("show" in text or "list" in text or "all" in text):
            return {
                "message": "",
                "tool_calls": [{"tool": "list_layers", "arguments": {"case_id": context.case_id}}],
                "clarification_required": False,
            }
        if "feature" in text and ("how many" in text or "count" in text or "list" in text or "show" in text):
            layer_id = numbers[0] if numbers and "layer" in text else context.layer_id
            return {
                "message": "",
                "tool_calls": [{"tool": "list_features", "arguments": {"case_id": context.case_id, "layer_id": layer_id}}],
                "clarification_required": False,
            }
        if "feature" in text and numbers:
            return {
                "message": "",
                "tool_calls": [{"tool": "get_feature", "arguments": {"feature_id": numbers[0]}}],
                "clarification_required": False,
            }
        if "case" in text and ("list" in text or "show" in text):
            return {
                "message": "",
                "tool_calls": [{"tool": "list_cases", "arguments": {}}],
                "clarification_required": False,
            }
        if "comment" in text:
            return {
                "message": "",
                "tool_calls": [{"tool": "get_comments", "arguments": {"case_id": context.case_id, "layer_id": context.layer_id}}],
                "clarification_required": False,
            }
        if "buffer" in text:
            return {
                "message": "Buffer creation will be enabled in the mutation tool phase. For now I can inspect cases, layers, features, and comments.",
                "tool_calls": [],
                "clarification_required": False,
            }

        return {
            "message": "I need a little more detail. Please mention the case, layer, feature, or GIS operation you want.",
            "tool_calls": [],
            "clarification_required": True,
        }
