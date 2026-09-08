from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.feature.feature_websocket_manager import feature_connection_manager
from utils.dependencies import authorize_case
from utils.constants import WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.logger import logger

router = APIRouter(tags=["Features"])

# ===================================================
# LIVE FEATURE UPDATES (per case) — WebSocket
# ===================================================
# Broadcasts feature.created / feature.updated / feature.deleted to
# every client viewing this case's map. Does NOT send an initial
# snapshot on connect — the frontend is expected to already have
# loaded features via GET /cases/{case_id}/features before opening
# this connection; this is for live deltas only.

@router.websocket("/ws/cases/{case_id}/features")
async def case_feature_updates(websocket: WebSocket, case_id: int):
    """Push live feature.created/updated/deleted events to authenticated case subscribers."""
    token = websocket.query_params.get("token")
    payload = None
    if token:
        try:
            payload = await authorize_case(token, case_id)
        except Exception:
            payload = None
    if not payload or payload.get("user_id") is None or payload.get("email") is None:
        logger.warning(
            "Feature WebSocket authentication rejected | case_id=%s",
            case_id,
        )
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=WEBSOCKET_AUTH_REQUIRED)
        return

    await feature_connection_manager.connect(case_id, websocket)
    try:
        await websocket.send_json(
            {
                "event": "connection.ready",
                "case_id": case_id,
            }
        )
        while True:
            # Receiving keeps disconnect detection active. Feature
            # creation/edits/deletes remain on the existing authenticated
            # REST endpoints, which broadcast here after a successful write.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "Feature WebSocket closed unexpectedly | case_id=%s | error=%s",
            case_id,
            type(exc).__name__,
        )
    finally:
        feature_connection_manager.disconnect(case_id, websocket)