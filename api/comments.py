from fastapi import APIRouter, Depends, Form, File, UploadFile, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from services.comment_service import (
    create_comment,
    get_feature_comments,
    get_comment_attachment
)
from services.comment_websocket_manager import comment_connection_manager
from utils.auth_utils import decode_access_token
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_COMMENT
from utils.logger import logger

router = APIRouter(
    tags=["Comments"]
)

@router.post("/comments")
async def add_comment(
    feature_id: int = Form(...),
    comment: str = Form(...),
    attachment: UploadFile | None = File(
        None,
        description="Optional attachment: image (jpg/png/webp), PDF, DOCX, or plain text file."
    ),
    current_user=Depends(require_roles(CAN_COMMENT))
):
    logger.info(f"POST /comments | feature_id={feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")
    result = await run_in_threadpool(
        create_comment,
        feature_id,
        current_user["user_id"],
        comment,
        attachment,
    )
    await comment_connection_manager.broadcast(
        feature_id,
        {
            "event": "comment.created",
            "feature_id": feature_id,
            "comment_id": result["comment_id"],
        },
    )
    return result

@router.get("/features/{feature_id}/comments")
def list_feature_comments(feature_id: int, current_user=Depends(get_current_user)):

    logger.info(f"GET /features/{feature_id}/comments | user_id={current_user['user_id']}")

    return get_feature_comments(feature_id)

@router.get("/comments/{comment_id}/attachment")
def fetch_comment_attachment(comment_id: int, current_user=Depends(get_current_user)):

    logger.info(f"GET /comments/{comment_id}/attachment | user_id={current_user['user_id']}")

    return get_comment_attachment(comment_id)


@router.websocket("/ws/features/{feature_id}/comments")
async def feature_comment_updates(websocket: WebSocket, feature_id: int):
    """Push comment-created notifications to authenticated feature subscribers."""
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload or payload.get("user_id") is None or payload.get("sub") is None:
        logger.warning(
            "Comment WebSocket authentication rejected | feature_id=%s",
            feature_id,
        )
        await websocket.close(code=1008, reason="Authentication required")
        return

    await comment_connection_manager.connect(feature_id, websocket)
    try:
        await websocket.send_json(
            {
                "event": "connection.ready",
                "feature_id": feature_id,
            }
        )
        while True:
            # Receiving keeps disconnect detection active. Comment creation
            # remains on the existing authenticated REST endpoint.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "Comment WebSocket closed unexpectedly | feature_id=%s | error=%s",
            feature_id,
            type(exc).__name__,
        )
    finally:
        comment_connection_manager.disconnect(feature_id, websocket)
