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
from services.comment.serializers import _comment_to_dict

def get_feature_comments(case_id, layer_id, feature_number, db):

    logger.info(f"Fetching comments | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}")

    try:
        feature = db.scalar(
            select(Feature).where(
                Feature.case_id == case_id,
                Feature.feature_number == feature_number,
            )
        )
        if feature is None:
            logger.warning(
                f"Get feature comments failed: feature not found | case_id={case_id} | "
                f"feature_number={feature_number}"
            )
            raise NotFoundError(FEATURE_NOT_FOUND)

        if feature.layer_id != layer_id:
            logger.warning(
                f"Get feature comments failed: feature does not belong to layer | case_id={case_id} | "
                f"layer_id={layer_id} | feature_number={feature_number} | actual_layer_id={feature.layer_id}"
            )
            raise NotFoundError(LAYER_NOT_FOUND)

        result = db.execute(
            select(Comment.id)
            .where(Comment.feature_id == feature.id)
            .order_by(Comment.created_at.asc())
        )

        comments = [{"id": row.id} for row in result]

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch comments | case_id={case_id} | feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(COMMENT_FETCH_FAILED) from e

    return comments


# ===================================================
# GET COMMENT THREAD FOR A FEATURE (unlimited nesting)
# ===================================================
# Fetches the full nested thread in one recursive query: every
# top-level comment for this feature, plus every reply (and reply of
# reply, unlimited depth) beneath them — then assembles the nested
# tree structure in Python from the flat rows returned.

def get_feature_comment_thread(case_id, layer_id, feature_number, db):

    logger.info(
        f"Fetching comment thread | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}"
    )

    try:
        feature = db.scalar(
            select(Feature).where(
                Feature.case_id == case_id,
                Feature.feature_number == feature_number,
            )
        )
        if feature is None:
            logger.warning(
                f"Get feature comment thread failed: feature not found | case_id={case_id} | "
                f"feature_number={feature_number}"
            )
            raise NotFoundError(FEATURE_NOT_FOUND)

        if feature.layer_id != layer_id:
            logger.warning(
                f"Get feature comment thread failed: feature does not belong to layer | case_id={case_id} | "
                f"layer_id={layer_id} | feature_number={feature_number} | actual_layer_id={feature.layer_id}"
            )
            raise NotFoundError(LAYER_NOT_FOUND)

        rows = db.execute(
            text("""
                WITH RECURSIVE thread AS (
                    SELECT id, parent_comment_id, user_id, comment,
                           attachment_filename, attachment_content_type, created_at
                    FROM comments
                    WHERE feature_id = :feature_id AND parent_comment_id IS NULL

                    UNION ALL

                    SELECT c.id, c.parent_comment_id, c.user_id, c.comment,
                           c.attachment_filename, c.attachment_content_type, c.created_at
                    FROM comments c
                    INNER JOIN thread t ON c.parent_comment_id = t.id
                )
                SELECT * FROM thread ORDER BY created_at ASC
            """),
            {"feature_id": feature.id}
        ).mappings().all()

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch comment thread | case_id={case_id} | layer_id={layer_id} | "
            f"feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(COMMENT_FETCH_FAILED) from e

    nodes = {}
    roots = []

    for row in rows:
        node = {
            "id": row["id"],
            "user_id": row["user_id"],
            "comment": row["comment"],
            "has_attachment": row["attachment_filename"] is not None,
            "attachment_filename": row["attachment_filename"],
            "attachment_content_type": row["attachment_content_type"],
            "created_at": row["created_at"],
            "replies": [],
        }
        nodes[row["id"]] = node
        if row["parent_comment_id"] is None:
            roots.append(node)
        else:
            parent_node = nodes.get(row["parent_comment_id"])
            if parent_node:
                parent_node["replies"].append(node)

    return roots
