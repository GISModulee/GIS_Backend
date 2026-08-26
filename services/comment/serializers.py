from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from models.model import Comment, User, Feature, Case
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


# ===================================================
# SERIALIZATION HELPER
# ===================================================

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
    }
