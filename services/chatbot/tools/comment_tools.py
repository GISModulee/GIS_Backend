from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from services.chatbot.schemas import ToolDefinition, ToolResult
from services.comment.comment_service import get_feature_comment_thread, get_layer_comments


class GetCommentsInput(BaseModel):
    case_id: int | None = None
    layer_id: int | None = None


class GetCommentThreadInput(BaseModel):
    case_id: int | None = None
    layer_id: int | None = None
    feature_number: int | None = None


async def get_comments_tool(args: GetCommentsInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    layer_id = args.layer_id or context.layer_id or context.selected_layer_id
    if case_id is None or layer_id is None:
        return ToolResult(
            success=False,
            tool="get_comments",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case and layer."},
        )
    comments = get_layer_comments(case_id, layer_id, db)
    return ToolResult(success=True, tool="get_comments", data={"comments": comments, "count": len(comments)})


async def get_comment_thread_tool(args: GetCommentThreadInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    layer_id = args.layer_id or context.layer_id or context.selected_layer_id
    feature_number = args.feature_number or context.selected_feature_number
    if case_id is None or layer_id is None or feature_number is None:
        return ToolResult(
            success=False,
            tool="get_comment_thread",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case, layer, and feature number."},
        )
    thread = get_feature_comment_thread(case_id, layer_id, feature_number, db)
    return ToolResult(success=True, tool="get_comment_thread", data={"thread": thread, "count": len(thread)})


COMMENT_TOOLS = [
    ToolDefinition(
        name="get_comments",
        description="Get comments for a layer. Read-only.",
        input_model=GetCommentsInput,
        permission=None,
        confirmation_required=False,
        handler=get_comments_tool,
        side_effects="None",
    ),
    ToolDefinition(
        name="get_comment_thread",
        description="Get the existing nested comment thread for a feature. Read-only.",
        input_model=GetCommentThreadInput,
        permission=None,
        confirmation_required=False,
        handler=get_comment_thread_tool,
        side_effects="None",
    ),
]
