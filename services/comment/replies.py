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