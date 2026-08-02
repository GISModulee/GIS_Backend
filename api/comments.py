from fastapi import APIRouter, Depends, Form, File, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
 
from database.database import get_db
from services.comment.comment_service import (
    create_comment,
    get_feature_comments,
    get_comment_attachment,
    get_case_comments
)
from services.comment.comment_websocket_manager import comment_connection_manager
from schemas.comment_schema import CommentCreateResponse, CommentResponse
from utils.constants import WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.auth_utils import decode_access_token
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_COMMENT
from utils.logger import logger
 
router = APIRouter(
    tags=["Comments"]
)
 
@router.post("/comments", response_model=CommentCreateResponse)
async def add_comment(
    case_id: int = Form(...),
    feature_number: int = Form(...),
    comment: str = Form(...),
    attachment: UploadFile | None = File(
        None,
        description="Optional attachment: image (jpg/png/webp), PDF, DOCX, or plain text file."
    ),
    current_user=Depends(require_roles(CAN_COMMENT))
):
    logger.info(
        f"POST /comments | case_id={case_id} | feature_number={feature_number} | "
        f"user_id={current_user['user_id']} | role={current_user['role']}"
    )
    result = await run_in_threadpool(
        create_comment,
        case_id,
        feature_number,
        current_user["user_id"],
        comment,
        attachment,
    )
    await comment_connection_manager.broadcast(
        case_id,
        feature_number,
        {
            "event": "comment.created",
            "case_id": case_id,
            "feature_number": feature_number,
            "comment_id": result["comment_id"],
        },
    )
    return result
 
@router.get("/cases/{case_id}/features/{feature_number}/comments", response_model=list[CommentResponse])
def list_feature_comments(
    case_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
 
    logger.info(
        f"GET /cases/{case_id}/features/{feature_number}/comments | user_id={current_user['user_id']}"
    )
 
    return get_feature_comments(case_id, feature_number, db)
 
@router.get("/comments/{comment_id}/attachment")
def fetch_comment_attachment(comment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
 
    logger.info(f"GET /comments/{comment_id}/attachment | user_id={current_user['user_id']}")
 
    return get_comment_attachment(comment_id, db)
 
# ===================================================
# GET COMMENTS OF A CASE
# ===================================================
 
@router.get("/cases/{case_id}/comments", response_model=list[CommentResponse])
def list_case_comments(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
 
    logger.info(
        f"GET /cases/{case_id}/comments | user_id={current_user['user_id']}"
    )
 
    return get_case_comments(case_id, db)
 
 
@router.websocket("/ws/cases/{case_id}/features/{feature_number}/comments")
async def feature_comment_updates(websocket: WebSocket, case_id: int, feature_number: int):
    """Push comment-created notifications to authenticated feature subscribers."""
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload or payload.get("user_id") is None or payload.get("sub") is None:
        logger.warning(
            "Comment WebSocket authentication rejected | case_id=%s | feature_number=%s",
            case_id,
            feature_number,
        )
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=WEBSOCKET_AUTH_REQUIRED)
        return
 
    await comment_connection_manager.connect(case_id, feature_number, websocket)
    try:
        await websocket.send_json(
            {
                "event": "connection.ready",
                "case_id": case_id,
                "feature_number": feature_number,
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
            "Comment WebSocket closed unexpectedly | case_id=%s | feature_number=%s | error=%s",
            case_id,
            feature_number,
            type(exc).__name__,
        )
    finally:
        comment_connection_manager.disconnect(case_id, feature_number, websocket)
