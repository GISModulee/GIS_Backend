from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.database import engine
from utils.config import settings
from utils.logger import logger
from utils.exceptions import NotFoundError, ServiceUnavailableError
from services.comment_validator import CommentAttachmentValidator


# ===================================================
# CREATE COMMENT
# ===================================================
# `attachment` (renamed from `image`) now accepts image (jpg/png/webp),
# PDF, DOCX, or plain text — validated the same way GeoCLIP uploads
# are (extension check + magic-byte content check), not just
# rubber-stamped as "image/jpeg" like the old code did regardless of
# what was actually uploaded.

def create_comment(feature_id, user_id, comment, attachment: UploadFile | None = None):

    logger.info(
        f"Creating comment | feature_id={feature_id} | user_id={user_id} | "
        f"has_attachment={attachment is not None}"
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
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    INSERT INTO comments
                    (
                        feature_id,
                        user_id,
                        comment,
                        attachment_data,
                        attachment_filename,
                        attachment_content_type
                    )
                    VALUES
                    (
                        :feature_id,
                        :user_id,
                        :comment,
                        :attachment_data,
                        :attachment_filename,
                        :attachment_content_type
                    )
                    RETURNING id
                """),
                {
                    "feature_id": feature_id,
                    "user_id": user_id,
                    "comment": comment,
                    "attachment_data": attachment_data,
                    "attachment_filename": attachment_filename,
                    "attachment_content_type": attachment_content_type,
                }
            )

            comment_id = result.scalar()

    except SQLAlchemyError as e:
        logger.error(f"Failed to create comment | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create comment") from e

    logger.info(f"Comment created | comment_id={comment_id} | feature_id={feature_id}")

    return {
        "success": True,
        "comment_id": comment_id,
        "message": "Comment added successfully"
    }


# ===================================================
# GET COMMENTS OF A FEATURE (multi-user thread)
# ===================================================
# Every comment on this feature_id, from every user who's commented on
# it, in one ordered list — this IS the multi-user behavior: User1's
# "hello" and User2's reply both live under the same feature_id and
# both show up here, in order, each tagged with who wrote it via the
# JOIN against `users`. Any authenticated user can read the thread
# (see api/comments.py's get_current_user dependency); anyone with
# CAN_COMMENT can add to it — nothing scopes a comment to only its
# author, so this was already structurally multi-user before, it just
# didn't tell you WHO said what. Now it does.

def get_feature_comments(feature_id):

    logger.info(f"Fetching comments | feature_id={feature_id}")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT
                        c.id,
                        c.feature_id,
                        c.user_id,
                        u.full_name AS user_full_name,
                        u.username AS user_username,
                        u.role AS user_role,
                        c.comment,
                        c.attachment_filename,
                        c.attachment_content_type,
                        c.created_at
                    FROM comments c
                    LEFT JOIN users u ON u.id = c.user_id
                    WHERE c.feature_id = :feature_id
                    ORDER BY c.created_at ASC
                """),
                {
                    "feature_id": feature_id
                }
            )

            comments = []

            for row in result:
                comments.append({
                    "id": row.id,
                    "feature_id": row.feature_id,
                    "user_id": row.user_id,
                    "user_full_name": row.user_full_name,
                    "user_username": row.user_username,
                    "user_role": row.user_role,
                    "comment": row.comment,
                    "has_attachment": row.attachment_filename is not None,
                    "attachment_filename": row.attachment_filename,
                    "attachment_content_type": row.attachment_content_type,
                    "created_at": row.created_at
                })

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch comments | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch comments") from e

    return comments


# ===================================================
# UPDATE COMMENT
# ===================================================

def update_comment(comment_id, comment):

    logger.info(f"Updating comment | comment_id={comment_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    UPDATE comments
                    SET comment = :comment
                    WHERE id = :id
                """),
                {
                    "id": comment_id,
                    "comment": comment.comment
                }
            )

            if result.rowcount == 0:
                logger.warning(f"Update comment failed: not found | comment_id={comment_id}")
                raise NotFoundError("Comment not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to update comment | comment_id={comment_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update comment") from e

    logger.info(f"Comment updated | comment_id={comment_id}")

    return {
        "success": True,
        "message": "Comment updated successfully"
    }


# ===================================================
# DELETE COMMENT
# ===================================================

def delete_comment(comment_id):

    logger.info(f"Deleting comment | comment_id={comment_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    DELETE FROM comments
                    WHERE id = :id
                """),
                {
                    "id": comment_id
                }
            )

            if result.rowcount == 0:
                logger.warning(f"Delete comment failed: not found | comment_id={comment_id}")
                raise NotFoundError("Comment not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to delete comment | comment_id={comment_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete comment") from e

    logger.info(f"Comment deleted | comment_id={comment_id}")

    return {
        "success": True,
        "message": "Comment deleted successfully"
    }


# ===================================================
# GET COMMENT ATTACHMENT
# ===================================================
# RENAMED from get_comment_image — previously always served the blob
# back as "image/jpeg" no matter what was actually stored, which was
# already wrong for any non-JPEG image and would have been actively
# broken for PDFs/DOCX/text. Now serves the real content_type, and
# sets Content-Disposition with the original filename so a PDF/DOCX
# downloads or opens correctly instead of arriving as an unnamed blob.

def get_comment_attachment(comment_id):

    logger.info(f"Fetching comment attachment | comment_id={comment_id}")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT attachment_data, attachment_filename, attachment_content_type
                    FROM comments
                    WHERE id = :id
                """),
                {
                    "id": comment_id
                }
            )

            row = result.fetchone()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch comment attachment | comment_id={comment_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch comment attachment") from e

    if row is None:
        logger.warning(f"Comment attachment fetch failed: comment not found | comment_id={comment_id}")
        raise NotFoundError("Comment not found")

    if row.attachment_data is None:
        logger.warning(f"Comment attachment fetch failed: no attachment | comment_id={comment_id}")
        raise NotFoundError("No attachment found")

    return Response(
        content=row.attachment_data,
        media_type=row.attachment_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{row.attachment_filename}"'
        }
    )
