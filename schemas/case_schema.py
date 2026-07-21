from pydantic import BaseModel
from typing import Optional


class CaseCreate(BaseModel):
    title: str
    description: str
    priority: str
    created_by: int


# ===================================================
# PATCH CASE
# ===================================================

class CasePatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
