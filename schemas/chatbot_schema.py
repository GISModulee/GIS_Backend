from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    case_id: int | None = None
    layer_id: int | None = None
    selected_feature_id: int | None = None
    selected_feature_number: int | None = None
    selected_layer_id: int | None = None
    selected_features: list[int] = Field(default_factory=list)
    map_center: list[float] | None = None
    map_zoom: float | None = None
    visible_layers: list[int] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    context: ChatContext = Field(default_factory=ChatContext)
    confirmation_token: str | None = None


class ChatToolCall(BaseModel):
    tool: str
    status: Literal["success", "error", "pending_confirmation", "clarification_required"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class PendingActionResponse(BaseModel):
    token: str
    tool: str
    arguments: dict[str, Any]
    expires_at: datetime
    message: str


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    tool_calls: list[ChatToolCall] = Field(default_factory=list)
    map_events: list[dict[str, Any]] = Field(default_factory=list)
    pending_action: PendingActionResponse | None = None
