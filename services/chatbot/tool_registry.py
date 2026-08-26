from __future__ import annotations

from services.chatbot.schemas import ToolDefinition
from services.chatbot.tools import CASE_TOOLS, COMMENT_TOOLS, FEATURE_TOOLS, LAYER_TOOLS


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def ollama_schemas(self) -> list[dict]:
        return [tool.ollama_schema() for tool in self.all()]


TOOL_REGISTRY = ToolRegistry([
    *CASE_TOOLS,
    *LAYER_TOOLS,
    *FEATURE_TOOLS,
    *COMMENT_TOOLS,
])
