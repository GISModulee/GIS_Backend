from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from services.chatbot.schemas import ToolDefinition, ToolResult
from services.layer.layer_service import get_case_layers, get_layer, get_layers
from utils.constants import LAYER_NOT_FOUND
from utils.exceptions import NotFoundError


class GetLayerInput(BaseModel):
    layer_id: int | None = None


class ListLayersInput(BaseModel):
    case_id: int | None = None


async def get_layer_tool(args: GetLayerInput, db, current_user: dict[str, Any], context) -> ToolResult:
    layer_id = args.layer_id or context.layer_id or context.selected_layer_id
    if layer_id is None:
        return ToolResult(
            success=False,
            tool="get_layer",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide or select a layer."},
        )
    layer = await get_layer(layer_id, db)
    if layer is None:
        raise NotFoundError(LAYER_NOT_FOUND)
    return ToolResult(success=True, tool="get_layer", data={"layer": layer})


async def list_layers_tool(args: ListLayersInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    layers = await get_case_layers(case_id, db) if case_id is not None else await get_layers(db)
    return ToolResult(success=True, tool="list_layers", data={"layers": layers, "count": len(layers)})


LAYER_TOOLS = [
    ToolDefinition(
        name="get_layer",
        description="Get a single layer by id. Read-only.",
        input_model=GetLayerInput,
        permission=None,
        confirmation_required=False,
        handler=get_layer_tool,
        side_effects="None",
    ),
    ToolDefinition(
        name="list_layers",
        description="List all layers or layers for a case. Read-only.",
        input_model=ListLayersInput,
        permission=None,
        confirmation_required=False,
        handler=list_layers_tool,
        side_effects="None",
    ),
]
