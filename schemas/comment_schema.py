from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# ===================================================
# CREATE COMMENT
# ===================================================

class CommentCreateResponse(BaseModel):
    success: bool
    comment_id: int
    case_id: int
    layer_id: int
    feature_number: int
    message: str


# ===================================================
# CREATE REPLY
# ===================================================

class ReplyCreateResponse(BaseModel):
    success: bool
    comment_id: int
    parent_comment_id: int
    case_id: int
    layer_id: int
    feature_number: int
    message: str


# ===================================================
# COMMENT RESPONSE (full detail — used by case/layer comment lists)
# ===================================================

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


# ===================================================
# COMMENT ID ONLY (lightweight list — used by list_feature_comments)
# ===================================================

class CommentIdResponse(BaseModel):
    id: int


# ===================================================
# COMMENT THREAD (nested replies, unlimited depth)
# ===================================================

class CommentThreadResponse(BaseModel):
    id: int
    user_id: int
    comment: str
    has_attachment: bool
    attachment_filename: str | None = None
    attachment_content_type: str | None = None
    created_at: datetime
    replies: list["CommentThreadResponse"] = []


CommentThreadResponse.model_rebuild()