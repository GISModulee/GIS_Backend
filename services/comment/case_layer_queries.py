from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, text
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
from services.comment.serializers import _comment_to_dict

def get_case_comments(case_id: int, db):

    logger.info(
        f"Fetching comments for case | case_id={case_id}"
    )

    try:
        comments = db.scalars(
            select(Comment)
            .where(
                Comment.case_id == case_id
            )
            .order_by(
                Comment.created_at.desc()
            )
        ).all()

        return [
            _comment_to_dict(comment)
            for comment in comments
        ]

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed fetching case comments | case_id={case_id} | error={e}",
            exc_info=True
        )

        raise ServiceUnavailableError(
            COMMENT_FETCH_FAILED
        ) from e


# ===================================================
# GET COMMENTS OF A LAYER (scoped to case)
# ===================================================

def get_layer_comments(case_id: int, layer_id: int, db):

    logger.info(
        f"Fetching comments for layer | case_id={case_id} | layer_id={layer_id}"
    )

    try:
        reply_counts = (
            select(
                Comment.root_comment_id.label("root_comment_id"),
                func.count(Comment.id).label("reply_count"),
            )
            .where(Comment.root_comment_id.is_not(None))
            .group_by(Comment.root_comment_id)
            .subquery()
        )

        rows = db.execute(
            select(
                Comment,
                func.coalesce(reply_counts.c.reply_count, 0).label("reply_count"),
            )
            .outerjoin(reply_counts, reply_counts.c.root_comment_id == Comment.id)
            .where(
                Comment.case_id == case_id,
                Comment.layer_id == layer_id,
                Comment.parent_comment_id.is_(None),
            )
            .order_by(Comment.created_at.desc())
        ).all()

        comments = []
        for comment, reply_count in rows:
            item = _comment_to_dict(comment)
            item["reply_count"] = reply_count
            comments.append(item)
        return comments

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed fetching layer comments | case_id={case_id} | layer_id={layer_id} | error={e}",
            exc_info=True
        )

        raise ServiceUnavailableError(
            COMMENT_FETCH_FAILED
        ) from e
