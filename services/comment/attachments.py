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

def get_comment_attachment(case_id, layer_id, feature_number, comment_id, db):

    logger.info(
        f"Fetching comment attachment | case_id={case_id} | layer_id={layer_id} | "
        f"feature_number={feature_number} | comment_id={comment_id}"
    )

    try:
        row = db.execute(
            select(
                Comment.case_id,
                Comment.layer_id,
                Comment.feature_number,
                Comment.attachment_data,
                Comment.attachment_filename,
                Comment.attachment_content_type,
            ).where(Comment.id == comment_id)
        ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch comment attachment | comment_id={comment_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(COMMENT_ATTACHMENT_FETCH_FAILED) from e

    if row is None:
        logger.warning(f"Comment attachment fetch failed: comment not found | comment_id={comment_id}")
        raise NotFoundError(COMMENT_NOT_FOUND)

    if row.case_id != case_id or row.layer_id != layer_id or row.feature_number != feature_number:
        logger.warning(
            f"Comment attachment fetch failed: case/layer/feature mismatch | comment_id={comment_id} | "
            f"expected case_id={row.case_id} layer_id={row.layer_id} feature_number={row.feature_number} | "
            f"got case_id={case_id} layer_id={layer_id} feature_number={feature_number}"
        )
        raise NotFoundError(COMMENT_NOT_FOUND)

    if row.attachment_data is None:
        logger.warning(f"Comment attachment fetch failed: no attachment | comment_id={comment_id}")
        raise NotFoundError(COMMENT_ATTACHMENT_NOT_FOUND)

    return Response(
        content=row.attachment_data,
        media_type=row.attachment_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{row.attachment_filename}"'
        }
    )

