from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from services.case.case_service import get_case, get_cases
from services.chatbot.schemas import ToolDefinition, ToolResult
from utils.constants import CASE_NOT_FOUND
from utils.exceptions import NotFoundError


class GetCaseInput(BaseModel):
    case_id: int | None = None


class ListCasesInput(BaseModel):
    pass


async def get_case_tool(args: GetCaseInput, db, current_user: dict[str, Any], context) -> ToolResult:
    case_id = args.case_id or context.case_id
    if case_id is None:
        return ToolResult(
            success=False,
            tool="get_case",
            error={"code": "CLARIFICATION_REQUIRED", "message": "Please provide a case."},
        )
    case = await get_case(case_id, db)
    if case is None:
        raise NotFoundError(CASE_NOT_FOUND)
    return ToolResult(success=True, tool="get_case", data={"case": case})


async def list_cases_tool(args: ListCasesInput, db, current_user: dict[str, Any], context) -> ToolResult:
    cases = await get_cases(db)
    return ToolResult(success=True, tool="list_cases", data={"cases": cases, "count": len(cases)})


CASE_TOOLS = [
    ToolDefinition(
        name="get_case",
        description="Get a single case. Read-only.",
        input_model=GetCaseInput,
        permission=None,
        confirmation_required=False,
        handler=get_case_tool,
        side_effects="None",
    ),
    ToolDefinition(
        name="list_cases",
        description="List cases. Read-only.",
        input_model=ListCasesInput,
        permission=None,
        confirmation_required=False,
        handler=list_cases_tool,
        side_effects="None",
    ),
]
