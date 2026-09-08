from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from models.model import Comment
from utils.config import settings
from utils.constants import (
    CASE_NOT_FOUND,
    COMMENT_ATTACHMENT_FETCH_FAILED,
    COMMENT_ATTACHMENT_NOT_FOUND,
    COMMENT_CREATE_FAILED,
    COMMENT_DELETE_FAILED,
    COMMENT_FETCH_FAILED,
    COMMENT_NOT_FOUND,
    FEATURE_NOT_FOUND,
    LAYER_NOT_FOUND,
)
from utils.logger import logger
from utils.exceptions import NotFoundError, ServiceUnavailableError
from services.comment.comment_validator import CommentAttachmentValidator


_author_cache: dict[int, dict[str, str | None]] = {}


def remember_comment_author(user_context: dict | None) -> dict[str, str | None]:
    """Keep best-effort CI user display data for later comment reads."""
    if not user_context:
        return _empty_author()

    user_id = user_context.get("user_id")
    first_name = user_context.get("first_name")
    last_name = user_context.get("last_name")
    email = user_context.get("email")
    username = user_context.get("username") or user_context.get("user_username") or email
    full_name = user_context.get("user_full_name") or " ".join(
        part for part in (first_name, last_name) if part
    ).strip() or None

    author = {
        "user_full_name": full_name,
        "user_first_name": first_name,
        "user_last_name": last_name,
        "user_email": email,
        "username": username,
        # Kept for existing frontend compatibility.
        "user_username": username,
        "user_role": user_context.get("role") or user_context.get("user_role"),
    }
    if user_id is not None:
        _author_cache[int(user_id)] = author
    return author


def _empty_author() -> dict[str, str | None]:
    return {
        "user_full_name": None,
        "user_first_name": None,
        "user_last_name": None,
        "user_email": None,
        "username": None,
        "user_username": None,
        "user_role": None,
    }


def _author_for_user(user_id: int | None) -> dict[str, str | None]:
    if user_id is None:
        return _empty_author()
    return _author_cache.get(int(user_id), _empty_author())

def _comment_to_dict(comment):
    return {
        "id": comment.id,
        "feature_id": comment.feature_id,
        "feature_number": comment.feature_number,
        "layer_id": comment.layer_id,
        "case_id": comment.case_id,
        "user_id": comment.user_id,
        "parent_comment_id": comment.parent_comment_id,
        "root_comment_id": comment.root_comment_id,
        "comment": comment.comment,
        "has_attachment": comment.attachment_filename is not None,
        "attachment_filename": comment.attachment_filename,
        "attachment_content_type": comment.attachment_content_type,
        "created_at": comment.created_at,
        **_author_for_user(comment.user_id),
    }
