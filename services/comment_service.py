from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
 
from database.database import SessionLocal
from models.model import Comment, User, Feature, Case
from utils.config import settings
from utils.logger import logger
from utils.exceptions import NotFoundError, ServiceUnavailableError
from services.comment_validator import CommentAttachmentValidator
 
 
# ===================================================
# SERIALIZATION HELPER
# ===================================================
 
def _comment_to_dict(comment):
    return {
        "id": comment.id,
        "feature_id": comment.feature_id,
        "layer_id": comment.layer_id,
        "case_id": comment.case_id,
        "user_id": comment.user_id,
        "comment": comment.comment,
        "has_attachment": comment.attachment_filename is not None,
        "attachment_filename": comment.attachment_filename,
        "attachment_content_type": comment.attachment_content_type,
        "created_at": comment.created_at,
    }
 
 
def create_comment(case_id, feature_number, user_id, comment, attachment: UploadFile | None = None):
 
    logger.info(
        f"Creating comment | case_id={case_id} | feature_number={feature_number} | user_id={user_id} | "
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
                raise NotFoundError("Feature not found")
 
            new_comment = Comment(
                feature_id=feature.id,
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
            comment_id = new_comment.id
 
    except NotFoundError:
        raise
 
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to create comment | case_id={case_id} | feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError("Failed to create comment") from e
 
    logger.info(
        f"Comment created | comment_id={comment_id} | case_id={case_id} | feature_number={feature_number}"
    )
 
    return {
        "success": True,
        "comment_id": comment_id,
        "case_id": case_id,
        "feature_number": feature_number,
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
#
# FIX: previously ran the query with no check that feature_id exists.
# A nonexistent feature_id returned an empty list `[]` — indistinguishable
# from a real feature with zero comments. Now verifies the feature
# exists first and raises NotFoundError (404) if not.
 
def get_feature_comments(case_id, feature_number, db):
 
    logger.info(f"Fetching comments | case_id={case_id} | feature_number={feature_number}")
 
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
            raise NotFoundError("Feature not found")
 
        result = db.execute(
            select(
                Comment.id,
                Comment.user_id,
                User.full_name.label("user_full_name"),
                User.username.label("user_username"),
                User.role.label("user_role"),
                Comment.comment,
                Comment.attachment_filename,
                Comment.attachment_content_type,
                Comment.created_at,
            )
            .outerjoin(User, User.id == Comment.user_id)
            .where(Comment.feature_id == feature.id)
            .order_by(Comment.created_at.asc())
        )
        comments = []
        for row in result:
            comments.append({
                "id": row.id,
                "case_id": case_id,
                "feature_number": feature_number,
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
 
    except NotFoundError:
        raise
 
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch comments | case_id={case_id} | feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError("Failed to fetch comments") from e
 
    return comments
 
 
# ===================================================
# UPDATE COMMENT
# ===================================================
# NOTE: not currently wired to any route in api/comments.py — flagging
# as dead code per your request rather than silently changing routing.
# Exception handling here is already correct and needs no fix.
 
def update_comment(comment_id, comment):
 
    logger.info(f"Updating comment | comment_id={comment_id}")
 
    try:
        with SessionLocal.begin() as db:
            existing = db.get(Comment, comment_id)
            if existing is None:
                logger.warning(f"Update comment failed: not found | comment_id={comment_id}")
                raise NotFoundError("Comment not found")
            existing.comment = comment.comment
 
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
                raise NotFoundError("Comment not found")
            db.delete(existing)
 
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
 
def get_comment_attachment(comment_id, db):
 
    logger.info(f"Fetching comment attachment | comment_id={comment_id}")
 
    try:
        row = db.execute(
            select(
                Comment.attachment_data,
                Comment.attachment_filename,
                Comment.attachment_content_type,
            ).where(Comment.id == comment_id)
        ).one_or_none()
 
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
            raise NotFoundError("Case not found")
 
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
            "Failed to fetch comments"
        ) from e
