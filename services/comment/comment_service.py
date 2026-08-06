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
        "comment": comment.comment,
        "has_attachment": comment.attachment_filename is not None,
        "attachment_filename": comment.attachment_filename,
        "attachment_content_type": comment.attachment_content_type,
        "created_at": comment.created_at,
    }


def create_comment(case_id, layer_id, feature_number, user_id, comment, attachment: UploadFile | None = None):

    logger.info(
        f"Creating comment | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number} | "
        f"user_id={user_id} | has_attachment={attachment is not None}"
    )

    attachment_data = None
    attachment_filename = None
    attachment_content_type = None

    if attachment is not None:

        CommentAttachmentValidator.validate_extension(attachment.filename)

        attachment.file.seek(0)
        content = attachment.file.read()

        CommentAttachmentValidator.validate_size(content, settings.MAX_FILE_SIZE_BYTES)
        _, detected_mime = CommentAttachmentValidator.validate_magic_bytes(content, attachment.filename)

        attachment_data = content
        attachment_filename = attachment.filename
        attachment_content_type = detected_mime

    try:
        with SessionLocal.begin() as db:
            feature = db.scalar(
                select(Feature).where(
                    Feature.case_id == case_id,
                    Feature.feature_number == feature_number,
                )
            )
            if feature is None:
                logger.warning(
                    f"Create comment failed: feature not found | case_id={case_id} | "
                    f"feature_number={feature_number}"
                )
                raise NotFoundError(FEATURE_NOT_FOUND)

            if feature.layer_id != layer_id:
                logger.warning(
                    f"Create comment failed: feature does not belong to layer | case_id={case_id} | "
                    f"layer_id={layer_id} | feature_number={feature_number} | actual_layer_id={feature.layer_id}"
                )
                raise NotFoundError(LAYER_NOT_FOUND)

            new_comment = Comment(
                feature_id=feature.id,
                feature_number=feature.feature_number,
                layer_id=feature.layer_id,
                case_id=feature.case_id,
                user_id=user_id,
                comment=comment,
                attachment_data=attachment_data,
                attachment_filename=attachment_filename,
                attachment_content_type=attachment_content_type,
            )
            db.add(new_comment)
            db.flush()
            db.refresh(new_comment)

            # Fetch the author's display info now, while the session is
            # still open — needed to build the full comment object below.
            user = db.get(User, user_id)

            comment_id = new_comment.id
            full_comment = {
                "id": new_comment.id,
                "parent_comment_id": None,
                "case_id": new_comment.case_id,
                "layer_id": new_comment.layer_id,
                "feature_number": new_comment.feature_number,
                "user_id": new_comment.user_id,
                "user_full_name": user.full_name if user else None,
                "user_username": user.username if user else None,
                "user_role": user.role if user else None,
                "comment": new_comment.comment,
                "has_attachment": new_comment.attachment_filename is not None,
                "attachment_filename": new_comment.attachment_filename,
                "attachment_content_type": new_comment.attachment_content_type,
                "created_at": new_comment.created_at,
                "replies": [],
            }

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to create comment | case_id={case_id} | feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(COMMENT_CREATE_FAILED) from e

    logger.info(
        f"Comment created | comment_id={comment_id} | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}"
    )

    return {
        "success": True,
        "comment_id": comment_id,
        "case_id": case_id,
        "layer_id": layer_id,
        "feature_number": feature_number,
        "message": "Comment added successfully",
        "comment": full_comment,
    }


# ===================================================
# CREATE REPLY (nested, unlimited depth)
# ===================================================
# Replies carry the same feature_id/feature_number/case_id/layer_id as
# any top-level comment (denormalized from the feature), plus a
# parent_comment_id pointing at whichever comment they're replying to
# — which can itself be a top-level comment or another reply, allowing
# unlimited nesting depth.

def create_reply(case_id, layer_id, feature_number, parent_comment_id, user_id, comment, attachment: UploadFile | None = None):

    logger.info(
        f"Creating reply | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number} | "
        f"parent_comment_id={parent_comment_id} | user_id={user_id} | has_attachment={attachment is not None}"
    )

    attachment_data = None
    attachment_filename = None
    attachment_content_type = None

    if attachment is not None:

        CommentAttachmentValidator.validate_extension(attachment.filename)

        attachment.file.seek(0)
        content = attachment.file.read()

        CommentAttachmentValidator.validate_size(content, settings.MAX_FILE_SIZE_BYTES)
        _, detected_mime = CommentAttachmentValidator.validate_magic_bytes(content, attachment.filename)

        attachment_data = content
        attachment_filename = attachment.filename
        attachment_content_type = detected_mime

    try:
        with SessionLocal.begin() as db:
            feature = db.scalar(
                select(Feature).where(
                    Feature.case_id == case_id,
                    Feature.feature_number == feature_number,
                )
            )
            if feature is None:
                logger.warning(
                    f"Create reply failed: feature not found | case_id={case_id} | "
                    f"feature_number={feature_number}"
                )
                raise NotFoundError(FEATURE_NOT_FOUND)

            if feature.layer_id != layer_id:
                logger.warning(
                    f"Create reply failed: feature does not belong to layer | case_id={case_id} | "
                    f"layer_id={layer_id} | feature_number={feature_number} | actual_layer_id={feature.layer_id}"
                )
                raise NotFoundError(LAYER_NOT_FOUND)

            parent = db.get(Comment, parent_comment_id)
            if parent is None:
                logger.warning(
                    f"Create reply failed: parent comment not found | parent_comment_id={parent_comment_id}"
                )
                raise NotFoundError(COMMENT_NOT_FOUND)

            if parent.feature_id != feature.id:
                logger.warning(
                    f"Create reply failed: parent comment belongs to a different feature | "
                    f"parent_comment_id={parent_comment_id} | parent_feature_id={parent.feature_id} | "
                    f"expected_feature_id={feature.id}"
                )
                raise NotFoundError(COMMENT_NOT_FOUND)

            new_reply = Comment(
                feature_id=feature.id,
                feature_number=feature.feature_number,
                layer_id=feature.layer_id,
                case_id=feature.case_id,
                parent_comment_id=parent_comment_id,
                user_id=user_id,
                comment=comment,
                attachment_data=attachment_data,
                attachment_filename=attachment_filename,
                attachment_content_type=attachment_content_type,
            )
            db.add(new_reply)
            db.flush()
            db.refresh(new_reply)

            user = db.get(User, user_id)

            reply_id = new_reply.id
            full_comment = {
                "id": new_reply.id,
                "parent_comment_id": new_reply.parent_comment_id,
                "case_id": new_reply.case_id,
                "layer_id": new_reply.layer_id,
                "feature_number": new_reply.feature_number,
                "user_id": new_reply.user_id,
                "user_full_name": user.full_name if user else None,
                "user_username": user.username if user else None,
                "user_role": user.role if user else None,
                "comment": new_reply.comment,
                "has_attachment": new_reply.attachment_filename is not None,
                "attachment_filename": new_reply.attachment_filename,
                "attachment_content_type": new_reply.attachment_content_type,
                "created_at": new_reply.created_at,
                "replies": [],
            }

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to create reply | parent_comment_id={parent_comment_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(COMMENT_CREATE_FAILED) from e

    logger.info(
        f"Reply created | comment_id={reply_id} | parent_comment_id={parent_comment_id} | "
        f"case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}"
    )

    return {
        "success": True,
        "comment_id": reply_id,
        "parent_comment_id": parent_comment_id,
        "case_id": case_id,
        "layer_id": layer_id,
        "feature_number": feature_number,
        "message": "Reply added successfully",
        "comment": full_comment,
    }


# ===================================================
# GET COMMENTS OF A FEATURE (multi-user thread)
# ===================================================
# UPDATED: now returns only comment IDs (not full comment bodies) —
# lightweight "which comments exist on this feature" check.
# No more User join needed for this endpoint.

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


# ===================================================
# UPDATE COMMENT
# ===================================================
# NOTE: not currently wired to any route in api/comments.py — flagging
# as dead code per your request rather than silently changing routing.
# Exception handling here is already correct and needs no fix.

# ===================================================
# DELETE COMMENT
# ===================================================
# NOTE: not currently wired to any route in api/comments.py — flagging
# as dead code per your request rather than silently changing routing.
# Exception handling here is already correct and needs no fix.

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


# ===================================================
# GET COMMENT ATTACHMENT
# ===================================================
# UPDATED: now takes case_id, layer_id, and feature_number from the
# URL and validates all three directly against the comment's own
# stored columns — no Feature join needed now that feature_number is
# denormalized onto Comment.

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


# ===================================================
# GET COMMENTS OF A CASE
# ===================================================

def get_case_comments(case_id: int, db):

    logger.info(
        f"Fetching comments for case | case_id={case_id}"
    )

    try:
        case_exists = db.scalar(
            select(Case.id).where(
                Case.id == case_id
            )
        )

        if case_exists is None:
            logger.warning(
                f"Get case comments failed: case not found | case_id={case_id}"
            )
            raise NotFoundError(CASE_NOT_FOUND)

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
        case_exists = db.scalar(
            select(Case.id).where(Case.id == case_id)
        )

        if case_exists is None:
            logger.warning(
                f"Get layer comments failed: case not found | case_id={case_id}"
            )
            raise NotFoundError(CASE_NOT_FOUND)

        comments = db.scalars(
            select(Comment)
            .where(
                Comment.case_id == case_id,
                Comment.layer_id == layer_id,
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
            f"Failed fetching layer comments | case_id={case_id} | layer_id={layer_id} | error={e}",
            exc_info=True
        )

        raise ServiceUnavailableError(
            COMMENT_FETCH_FAILED
        ) from e