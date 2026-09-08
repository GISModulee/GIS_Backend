from fastapi import APIRouter, Depends, Form, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
 
from database.database import get_db
from models.model import Comment
from services.comment.comment_service import (
    create_comment,
    create_reply,
    delete_comment,
    get_feature_comments,
    get_feature_comment_thread,
    get_comment_attachment,
    get_case_comments,
    get_layer_comments,
)
from services.comment.comment_websocket_manager import comment_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager
from schemas.comment_schema import (
    CommentCreateResponse,
    CommentResponse,
    CommentIdResponse,
    CommentDeleteResponse,
    ReplyCreateResponse,
    CommentThreadResponse,
)
from utils.constants import COMMENT_NOT_FOUND, WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.dependencies import require_roles_for_case
from utils.roles import CAN_COMMENT
from utils.exceptions import NotFoundError
from utils.logger import logger
 
router = APIRouter(
    tags=["Comments"]
)
 
@router.post("/cases/{case_id}/layers/{layer_id}/comments", response_model=CommentCreateResponse)
async def add_comment(
    case_id: int,
    layer_id: int,
    feature_number: int = Form(...),
    comment: str = Form(...),
    attachment: UploadFile | None = File(
        None,
        description="Optional attachment: image (jpg/png/webp), PDF, DOCX, or plain text file."
    ),
    current_user=Depends(require_roles_for_case(CAN_COMMENT))
):
    logger.info(
        f"POST /cases/{case_id}/layers/{layer_id}/comments | feature_number={feature_number} | "
        f"user_id={current_user['user_id']} | role={current_user['role']}"
    )
    result = await run_in_threadpool(
        create_comment,
        case_id,
        layer_id,
        feature_number,
        current_user["user_id"],
        comment,
        attachment,
        None,
        current_user,
    )
    await comment_connection_manager.broadcast(
        case_id,
        feature_number,
        jsonable_encoder(
            {
                "event": "comment.created",
                "case_id": case_id,
                "layer_id": layer_id,
                "feature_number": feature_number,
                "comment": result["comment"],
            }
        ),
    )
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.comment_created",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature_number": feature_number,
            "comment_id": result["comment"]["id"],
            "has_comments": True,
        },
    )
    return result


# ===================================================
# ADD REPLY (nested, unlimited depth)
# ===================================================

@router.post("/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/reply", response_model=ReplyCreateResponse)
async def add_reply(
    case_id: int,
    layer_id: int,
    feature_number: int,
    parent_comment_id: int = Form(...),
    comment: str = Form(...),
    attachment: UploadFile | None = File(
        None,
        description="Optional attachment: image (jpg/png/webp), PDF, DOCX, or plain text file."
    ),
    current_user=Depends(require_roles_for_case(CAN_COMMENT))
):
    logger.info(
        f"POST /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/reply | "
        f"parent_comment_id={parent_comment_id} | user_id={current_user['user_id']} | role={current_user['role']}"
    )
    result = await run_in_threadpool(
        create_comment,
        case_id,
        layer_id,
        feature_number,
        current_user["user_id"],
        comment,
        attachment,
        parent_comment_id,
        current_user,
    )
    await comment_connection_manager.broadcast(
        case_id,
        feature_number,
        jsonable_encoder(
            {
                "event": "comment.reply_created",
                "case_id": case_id,
                "layer_id": layer_id,
                "feature_number": feature_number,
                "parent_comment_id": parent_comment_id,
                "root_comment_id": result["comment"].get("root_comment_id"),
                "reply_count_delta": 1,
                "comment": result["comment"],
            }
        ),
    )
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.comment_created",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature_number": feature_number,
            "comment_id": result["comment"]["id"],
            "parent_comment_id": parent_comment_id,
            "root_comment_id": result["comment"].get("root_comment_id"),
            "reply_count_delta": 1,
            "has_comments": True,
        },
    )
    return result


# ===================================================
# DELETE COMMENT
# ===================================================

@router.delete(
    "/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}",
    response_model=CommentDeleteResponse,
)
async def remove_comment(
    case_id: int,
    layer_id: int,
    feature_number: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_COMMENT)),
):
    logger.warning(
        f"DELETE /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id} | "
        f"user_id={current_user['user_id']} | role={current_user['role']}"
    )

    existing = db.get(Comment, comment_id)
    if (
        existing is None
        or existing.case_id != case_id
        or existing.layer_id != layer_id
        or existing.feature_number != feature_number
    ):
        logger.warning(
            f"Delete comment failed: not found or scope mismatch | case_id={case_id} | "
            f"layer_id={layer_id} | feature_number={feature_number} | comment_id={comment_id}"
        )
        raise NotFoundError(COMMENT_NOT_FOUND)

    result = await run_in_threadpool(delete_comment, comment_id)

    await comment_connection_manager.broadcast(
        case_id,
        feature_number,
        jsonable_encoder(
            {
                "event": "comment.deleted",
                "case_id": case_id,
                "layer_id": layer_id,
                "feature_number": feature_number,
                "comment_id": comment_id,
                "parent_comment_id": existing.parent_comment_id,
            }
        ),
    )

    return result

 
# ===================================================