from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from services.comment.comment_service import (
    get_comment_attachment,
    get_comment_replies,
    get_case_comments,
    get_feature_comment_thread,
    get_feature_comments,
    get_layer_comments,
)
from services.comment.serializers import remember_comment_author
from schemas.comment_schema import CommentResponse, CommentThreadResponse
from utils.dependencies import get_current_case_context
from utils.logger import logger

router = APIRouter(tags=["Comments"])


# GET COMMENTS OF A FEATURE (multi-user thread)
# ===================================================
# UPDATED: response_model switched from list[CommentResponse] to
# list[CommentIdResponse] — this endpoint now returns only comment
# IDs, since get_feature_comments in comment_service.py was updated
# to select only Comment.id. All other comment routes below are
# untouched and still return full CommentResponse objects.

@router.get("/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments", response_model=list[CommentResponse])
def list_feature_comments(
    case_id: int,
    layer_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):
 
    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments | user_id={current_user['user_id']}"
    )
    remember_comment_author(current_user)
 
    return get_feature_comments(case_id, layer_id, feature_number, db)


# ===================================================
# GET FULL COMMENT THREAD FOR A FEATURE (nested replies)
# ===================================================

@router.get(
    "/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/thread",
    response_model=list[CommentThreadResponse]
)
def list_feature_comment_thread(
    case_id: int,
    layer_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):

    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/thread | "
        f"user_id={current_user['user_id']}"
    )
    remember_comment_author(current_user)

    return get_feature_comment_thread(case_id, layer_id, feature_number, db)


@router.get(
    "/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/replies",
    response_model=list[CommentResponse],
)
def list_comment_replies(
    case_id: int,
    layer_id: int,
    feature_number: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context),
):

    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/replies | "
        f"user_id={current_user['user_id']}"
    )
    remember_comment_author(current_user)

    return get_comment_replies(case_id, layer_id, feature_number, comment_id, db)

 
@router.get("/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/attachment")
def fetch_comment_attachment(
    case_id: int,
    layer_id: int,
    feature_number: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):
 
    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/attachment | "
        f"user_id={current_user['user_id']}"
    )
 
    return get_comment_attachment(case_id, layer_id, feature_number, comment_id, db)
 
# ===================================================
# GET COMMENTS OF A CASE
# ===================================================
 
@router.get("/cases/{case_id}/comments", response_model=list[CommentResponse])
def list_case_comments(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):
 
    logger.info(
        f"GET /cases/{case_id}/comments | user_id={current_user['user_id']}"
    )
    remember_comment_author(current_user)
 
    return get_case_comments(case_id, db)


# ===================================================
# GET COMMENTS OF A LAYER
# ===================================================

@router.get("/cases/{case_id}/layers/{layer_id}/comments", response_model=list[CommentResponse])
def list_layer_comments(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):

    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/comments | user_id={current_user['user_id']}"
    )
    remember_comment_author(current_user)

    return get_layer_comments(case_id, layer_id, db)
