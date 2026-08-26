from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    tool: str
    data: dict[str, Any] = Field(default_factory=dict)
    map_event: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    permission: list[str] | None
    confirmation_required: bool
    handler: Callable[[BaseModel, Any, dict[str, Any], Any], Awaitable[ToolResult]]
    side_effects: str
    websocket_events: tuple[str, ...] = ()

    def ollama_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }
