from datetime import datetime

from pydantic import BaseModel
from typing import Optional


class CaseCreate(BaseModel):
    title: str
    description: str
    priority: str
    # NOTE: `created_by` intentionally NOT accepted from the client.
    # It's derived server-side from the authenticated user
    # (current_user['user_id']) in api/cases.py — the same pattern
    # comments.py already uses. Accepting it from the request body
    # would let any client claim any user created a case.


# ===================================================
# PATCH CASE
# ===================================================

class CasePatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None


class CaseResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    priority: str
    created_by: int | None = None
    created_at: datetime


class CaseCreateResponse(BaseModel):
    success: bool
    case_id: int
    message: str


class CaseActionResponse(BaseModel):
    success: bool
    message: str
