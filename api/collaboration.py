from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from models.model import User
from services.collaboration.cursor_websocket_manager import cursor_connection_manager
from utils.constants import WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.auth_utils import decode_access_token
from utils.logger import logger

router = APIRouter(tags=["Collaboration"])


@router.websocket("/ws/cases/{case_id}/cursors")
async def case_cursor_updates(websocket: WebSocket, case_id: int, db: Session = Depends(get_db)):
    """
    Bidirectional live cursor sharing for a case's map. Every connected
    client sends its own cursor position and receives everyone else's,
    labeled by user. Nothing here is persisted to the database.
    """
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload or payload.get("user_id") is None or payload.get("sub") is None:
        logger.warning("Cursor WebSocket authentication rejected | case_id=%s", case_id)
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=WEBSOCKET_AUTH_REQUIRED)
        return

    user_id = payload.get("user_id")

    # full_name isn't in the JWT payload — fetch it once on connect,
    # not on every cursor move.
    db_user = db.get(User, user_id)
    user_info = {
        "user_id": user_id,
        "user_full_name": db_user.full_name if db_user else None,
    }

    await cursor_connection_manager.connect(case_id, websocket, user_info)
    try:
        while True:
            data = await websocket.receive_json()

            lat = data.get("lat")
            lng = data.get("lng")
            if lat is None or lng is None:
                continue

            await cursor_connection_manager.broadcast_except(
                case_id,
                websocket,
                {
                    "event": "cursor.moved",
                    "user_id": user_info["user_id"],
                    "user_full_name": user_info["user_full_name"],
                    "lat": lat,
                    "lng": lng,
                },
            )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Cursor WebSocket closed unexpectedly | case_id=%s | error=%s", case_id, type(exc).__name__)
    finally:
        left_user = cursor_connection_manager.disconnect(case_id, websocket)
        if left_user:
            await cursor_connection_manager.broadcast_to_all(
                case_id,
                {"event": "cursor.left", "user_id": left_user["user_id"]},
            )