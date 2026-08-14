from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database.database import get_db
from services.comment.comment_service import get_feature_comment_thread
from services.comment.comment_websocket_manager import comment_connection_manager
from utils.auth_utils import decode_access_token
from utils.constants import WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.exceptions import NotFoundError
from utils.logger import logger

router = APIRouter(tags=["Comments"])


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
