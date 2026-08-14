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

def delete_comment(comment_id):

    logger.info(f"Deleting comment | comment_id={comment_id}")

    try:
        with SessionLocal.begin() as db:
            existing = db.get(Comment, comment_id)
            if existing is None:
                logger.warning(f"Delete comment failed: not found | comment_id={comment_id}")
                raise NotFoundError(COMMENT_NOT_FOUND)
            db.delete(existing)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to delete comment | comment_id={comment_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(COMMENT_DELETE_FAILED) from e

    logger.info(f"Comment deleted | comment_id={comment_id}")

    return {
        "success": True,
        "message": "Comment deleted successfully"
    }


