from fastapi import APIRouter, Depends, Form, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
 
from database.database import get_db
from services.comment.comment_service import (
    create_comment,
    create_reply,
    get_feature_comments,
    get_feature_comment_thread,
    get_comment_attachment,
    get_case_comments,
    get_layer_comments,
)
from services.comment.comment_websocket_manager import comment_connection_manager
from schemas.comment_schema import (
    CommentCreateResponse,
    CommentResponse,
    CommentIdResponse,
    ReplyCreateResponse,
    CommentThreadResponse,
)
from utils.constants import WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.auth_utils import decode_access_token
from utils.dependencies import get_current_user, require_roles
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
    current_user=Depends(require_roles(CAN_COMMENT))
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
    current_user=Depends(require_roles(CAN_COMMENT))
):
    logger.info(
        f"POST /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/reply | "
        f"parent_comment_id={parent_comment_id} | user_id={current_user['user_id']} | role={current_user['role']}"
    )
    result = await run_in_threadpool(
        create_reply,
        case_id,
        layer_id,
        feature_number,
        parent_comment_id,
        current_user["user_id"],
        comment,
        attachment,
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
                "comment": result["comment"],
            }
        ),
    )
    return result

 
# ===================================================
# GET COMMENTS OF A FEATURE (multi-user thread)
# ===================================================
# UPDATED: response_model switched from list[CommentResponse] to
# list[CommentIdResponse] — this endpoint now returns only comment
# IDs, since get_feature_comments in comment_service.py was updated
# to select only Comment.id. All other comment routes below are
# untouched and still return full CommentResponse objects.

@router.get("/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments", response_model=list[CommentIdResponse])
def list_feature_comments(
    case_id: int,
    layer_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
 
    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments | user_id={current_user['user_id']}"
    )
 
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
    current_user=Depends(get_current_user)
):

    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/thread | "
        f"user_id={current_user['user_id']}"
    )

    return get_feature_comment_thread(case_id, layer_id, feature_number, db)

 
@router.get("/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/attachment")
def fetch_comment_attachment(
    case_id: int,
    layer_id: int,
    feature_number: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
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
    current_user=Depends(get_current_user)
):
 
    logger.info(
        f"GET /cases/{case_id}/comments | user_id={current_user['user_id']}"
    )
 
    return get_case_comments(case_id, db)


# ===================================================
# GET COMMENTS OF A LAYER
# ===================================================

@router.get("/cases/{case_id}/layers/{layer_id}/comments", response_model=list[CommentResponse])
def list_layer_comments(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    logger.info(
        f"GET /cases/{case_id}/layers/{layer_id}/comments | user_id={current_user['user_id']}"
    )

    return get_layer_comments(case_id, layer_id, db)
 
 
@router.websocket("/ws/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments")
async def feature_comment_updates(
    websocket: WebSocket,
    case_id: int,
    layer_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
):
    """
    Authenticates the subscriber, sends the full comment thread once on
    connect (thread.initial), then pushes live comment.created and
    comment.reply_created events as they happen — no REST re-fetch
    needed after the initial connection.
    """
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload or payload.get("user_id") is None or payload.get("sub") is None:
        logger.warning(
            "Comment WebSocket authentication rejected | case_id=%s | layer_id=%s | feature_number=%s",
            case_id,
            layer_id,
            feature_number,
        )
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=WEBSOCKET_AUTH_REQUIRED)
        return
 
    await comment_connection_manager.connect(case_id, feature_number, websocket)
    try:
        # get_feature_comment_thread is sync (regular blocking SQLAlchemy
        # calls) — run it in a threadpool so this async WebSocket handler
        # doesn't block the event loop while the query runs.
        try:
            comments = await run_in_threadpool(
                get_feature_comment_thread,
                case_id,
                layer_id,
                feature_number,
                db,
            )
        except NotFoundError as exc:
            logger.warning(
                "Comment WebSocket thread fetch failed | case_id=%s | layer_id=%s | feature_number=%s | error=%s",
                case_id,
                layer_id,
                feature_number,
                type(exc).__name__,
            )
            await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=str(exc))
            return

        await websocket.send_json(
            jsonable_encoder(
                {
                    "event": "thread.initial",
                    "case_id": case_id,
                    "layer_id": layer_id,
                    "feature_number": feature_number,
                    "comments": comments,
                }
            )
        )
        while True:
            # Receiving keeps disconnect detection active. Comment creation
            # remains on the existing authenticated REST endpoints, which
            # broadcast full comment objects back over this connection.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "Comment WebSocket closed unexpectedly | case_id=%s | layer_id=%s | feature_number=%s | error=%s",
            case_id,
            layer_id,
            feature_number,
            type(exc).__name__,
        )
    finally:
        await comment_connection_manager.disconnect(case_id, feature_number, websocket)