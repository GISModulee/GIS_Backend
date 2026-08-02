from datetime import datetime

from pydantic import BaseModel


class CommentCreateResponse(BaseModel):
    success: bool
    comment_id: int
    case_id: int
    feature_number: int
    message: str


class CommentResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    comment: str
    has_attachment: bool
    attachment_filename: str | None = None
    attachment_content_type: str | None = None
    created_at: datetime
    feature_id: int | None = None
    feature_number: int | None = None
    layer_id: int | None = None
    user_full_name: str | None = None
    user_username: str | None = None
    user_role: str | None = None
