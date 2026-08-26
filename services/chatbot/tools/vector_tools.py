from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from services.chatbot.schemas import ToolDefinition, ToolResult
from services.vector.vector_services import buffer_feature, centroid_feature, convex_hull
from utils.roles import CAN_WRITE


class BufferInput(BaseModel):
    case_id: int | None = None
    feature_number: int | None = None
    distance: float
    layer_name: str | None = None


class CentroidInput(BaseModel):
    case_id: int | None = None
    feature_number: int | None = None
    layer_name: str | None = None


class ConvexHullInput(BaseModel):
    case_id: int | None = None
    feature_numbers: list[int]
    layer_name: str | None = None


async def buffer_tool(args: BufferInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    feature_number = args.feature_number or context.selected_feature_number
    if case_id is None or feature_number is None:
        return ToolResult(
            success=False,
            tool="buffer",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case and feature number."},
        )
    result = await buffer_feature(case_id, feature_number, args.distance, db, current_user["user_id"], args.layer_name)
    return ToolResult(success=True, tool="buffer", data=result, map_event={"type": "feature.created", **result})


async def centroid_tool(args: CentroidInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    feature_number = args.feature_number or context.selected_feature_number
    if case_id is None or feature_number is None:
        return ToolResult(
            success=False,
            tool="centroid",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case and feature number."},
        )
    result = await centroid_feature(case_id, feature_number, db, current_user["user_id"], args.layer_name)
    return ToolResult(success=True, tool="centroid", data=result, map_event={"type": "feature.created", **result})


async def convex_hull_tool(args: ConvexHullInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    if case_id is None:
        return ToolResult(
            success=False,
            tool="convex_hull",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case."},
        )
    result = await convex_hull(case_id, args.feature_numbers, db, current_user["user_id"], args.layer_name)
    return ToolResult(success=True, tool="convex_hull", data=result, map_event={"type": "feature.created", **result})


VECTOR_TOOLS = [
    ToolDefinition(
        name="buffer",
        description="Create a buffer around a feature number and save it as a vector result layer.",
        input_model=BufferInput,
        permission=CAN_WRITE,
        confirmation_required=True,
        handler=buffer_tool,
        side_effects="Creates a new vector layer and feature.",
        websocket_events=("layer.created", "feature.created"),
    ),
    ToolDefinition(
        name="centroid",
        description="Create a centroid result for a feature number and save it as a vector result layer.",
        input_model=CentroidInput,
        permission=CAN_WRITE,
        confirmation_required=True,
        handler=centroid_tool,
        side_effects="Creates a new vector layer and feature.",
        websocket_events=("layer.created", "feature.created"),
    ),
    ToolDefinition(
        name="convex_hull",
        description="Create a convex hull around feature numbers and save it as a vector result layer.",
        input_model=ConvexHullInput,
        permission=CAN_WRITE,
        confirmation_required=True,
        handler=convex_hull_tool,
        side_effects="Creates a new vector layer and feature.",
        websocket_events=("layer.created", "feature.created"),
    ),
]
