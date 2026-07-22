from fastapi import APIRouter, Depends, Form, File, UploadFile

from services.comment_service import (
    create_comment,
    get_feature_comments,
    get_comment_image
)
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_COMMENT
from utils.logger import logger

router = APIRouter(
    tags=["Comments"]
)


@router.post("/comments")
def add_comment(
    feature_id: int = Form(...),
    comment: str = Form(...),
    image: UploadFile | None = File(None),
    current_user=Depends(require_roles(CAN_COMMENT))
):
    logger.info(f"POST /comments | feature_id={feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")
    return create_comment(
        feature_id=feature_id,
        user_id=current_user["user_id"],
        comment=comment,
        image=image
    )


@router.get("/features/{feature_id}/comments")
def list_feature_comments(feature_id: int, current_user=Depends(get_current_user)):

    logger.info(f"GET /features/{feature_id}/comments | user_id={current_user['user_id']}")

    return get_feature_comments(feature_id)


@router.get("/comments/{comment_id}/image")
def fetch_comment_image(comment_id: int, current_user=Depends(get_current_user)):

    logger.info(f"GET /comments/{comment_id}/image | user_id={current_user['user_id']}")

    return get_comment_image(comment_id)
