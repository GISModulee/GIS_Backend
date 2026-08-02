from typing import Any

from pydantic import BaseModel


class UploadResponse(BaseModel):
    success: bool
    case_id: int
    filename: str
    file_type: str
    data: dict[str, Any]
