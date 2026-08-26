from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from services.chatbot.schemas import ToolDefinition, ToolResult
from services.feature.feature_service import get_case_features, get_feature, get_feature_by_number, get_layer_features
from utils.constants import FEATURE_NOT_FOUND
from utils.exceptions import NotFoundError


class GetFeatureInput(BaseModel):
    feature_id: int | None = None
    case_id: int | None = None
    layer_id: int | None = None
    feature_number: int | None = None


class ListFeaturesInput(BaseModel):
    case_id: int | None = None
    layer_id: int | None = None


async def get_feature_tool(args: GetFeatureInput, db, current_user: dict[str, Any], context) -> ToolResult:
    feature_id = args.feature_id or context.selected_feature_id
    if feature_id is not None:
        feature = await get_feature(feature_id, db)
    else:
        case_id = args.case_id or context.case_id
        layer_id = args.layer_id or context.layer_id or context.selected_layer_id
        feature_number = args.feature_number or context.selected_feature_number
        if case_id is None or layer_id is None or feature_number is None:
            return ToolResult(
                success=False,
                tool="get_feature",
                error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide or select a feature."},
            )
        feature = await get_feature_by_number(case_id, layer_id, feature_number, db)
    if feature is None:
        raise NotFoundError(FEATURE_NOT_FOUND)
    return ToolResult(success=True, tool="get_feature", data={"feature": feature})


async def list_features_tool(args: ListFeaturesInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    layer_id = args.layer_id or context.layer_id or context.selected_layer_id
    if layer_id is not None:
        features = await get_layer_features(layer_id, db)
    elif case_id is not None:
        features = await get_case_features(case_id, db)
    else:
        return ToolResult(
            success=False,
            tool="list_features",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case or layer."},
        )
    return ToolResult(success=True, tool="list_features", data={"features": features, "count": len(features)})


FEATURE_TOOLS = [
    ToolDefinition(
        name="get_feature",
        description="Get a single feature by id or by case/layer/feature number. Read-only.",
        input_model=GetFeatureInput,
        permission=None,
        confirmation_required=False,
        handler=get_feature_tool,
        side_effects="None",
    ),
    ToolDefinition(
        name="list_features",
        description="List features in a case or layer. Read-only.",
        input_model=ListFeaturesInput,
        permission=None,
        confirmation_required=False,
        handler=list_features_tool,
        side_effects="None",
    ),
]
