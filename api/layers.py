from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.layer_schema import LayerActionResponse, LayerCreate, LayerCreateResponse, LayerPatch, LayerResponse
from utils.constants import LAYER_NOT_FOUND, WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.exceptions import NotFoundError
from utils.dependencies import authorize_case, enforce_role, get_access_token, get_current_user, get_current_case_context, require_roles, require_roles_for_case
from utils.roles import CAN_WRITE, CAN_DELETE_OPERATIONAL
from services.layer.layer_service import (
    create_layer,
    get_layers,
    get_layer,
    update_layer,
    delete_layer,
    get_case_layers,
    patch_layer,
)
from services.layer.layer_websocket_manager import layer_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager
from utils.logger import logger

router = APIRouter(
    prefix="/layers",
    tags=["Layers"],
)


@router.post("", response_model=LayerCreateResponse)
async def add_layer(layer: LayerCreate, db: Session = Depends(get_db), access_token: str = Depends(get_access_token)):
    current_user = enforce_role(await authorize_case(access_token, layer.case_id), CAN_WRITE)
    logger.info(f"POST /layers | user_id={current_user['user_id']} | role={current_user['role']} | body={layer.model_dump()}")

    result = await create_layer(layer.model_dump(), db)

    created_layer = await get_layer(result["layer_id"], db)

    message = {
        "event": "layer.created",
        "case_id": created_layer["case_id"],
        "layer": created_layer,
    }

    await layer_connection_manager.broadcast(created_layer["case_id"], message)
    await feature_connection_manager.broadcast(created_layer["case_id"], message)

    return result


@router.get("", response_model=list[LayerResponse])
async def list_layers(case_id: int, db: Session = Depends(get_db), access_token: str = Depends(get_access_token)):
    current_user = await authorize_case(access_token, case_id)
    logger.info(f"GET /layers | user_id={current_user['user_id']} | case_id={case_id}")
    return await get_case_layers(case_id, db)


@router.get("/case/{case_id}", response_model=list[LayerResponse])
async def list_case_layers(case_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_case_context)):
    logger.info(f"GET /layers/case/{case_id} | user_id={current_user['user_id']}")
    return await get_case_layers(case_id, db)


@router.get("/case/{case_id}/{layer_id}", response_model=LayerResponse)
async def get_single_layer(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_case_context)
):
    logger.info(f"GET /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']}")

    layer = await get_layer(layer_id, db)

    if not layer or layer["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    return layer


@router.put("/case/{case_id}/{layer_id}", response_model=LayerActionResponse)
async def edit_layer(
    case_id: int,
    layer_id: int,
    layer: LayerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_WRITE))
):
    logger.info(f"PUT /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    result = await update_layer(layer_id, layer.model_dump(), db)

    updated_layer = await get_layer(layer_id, db)

    message = {
        "event": "layer.updated",
        "case_id": case_id,
        "layer_id": layer_id,
        "layer": updated_layer,
    }

    await layer_connection_manager.broadcast(case_id, message)
    await feature_connection_manager.broadcast(case_id, message)

    return result


@router.patch("/case/{case_id}/{layer_id}", response_model=LayerActionResponse)
async def edit_layer_partial(
    case_id: int,
    layer_id: int,
    layer: LayerPatch,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_WRITE))
):
    logger.info(f"PATCH /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    result = await patch_layer(layer_id, layer.model_dump(exclude_unset=True), db)

    updated_layer = await get_layer(layer_id, db)

    message = {
        "event": "layer.updated",
        "case_id": case_id,
        "layer_id": layer_id,
        "layer": updated_layer,
    }

    await layer_connection_manager.broadcast(case_id, message)
    await feature_connection_manager.broadcast(case_id, message)

    return result


@router.delete("/case/{case_id}/{layer_id}", response_model=LayerActionResponse)
async def remove_layer(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_DELETE_OPERATIONAL))
):
    logger.warning(f"DELETE /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    result = await delete_layer(layer_id, db)

    message = {
        "event": "layer.deleted",
        "case_id": case_id,
        "layer_id": layer_id,
    }

    await layer_connection_manager.broadcast(case_id, message)
    await feature_connection_manager.broadcast(case_id, message)

    return result


# ===================================================
# LIVE LAYER UPDATES (per case) — WebSocket
# ===================================================
# Broadcasts layer.created / layer.updated / layer.deleted to every
# client viewing this case's map. Does NOT send an initial snapshot on
# connect — the frontend is expected to already have loaded layers via
# GET /layers/case/{case_id} before opening this connection; this is
# for live deltas only.

@router.websocket("/ws/cases/{case_id}/layers")
async def case_layer_updates(websocket: WebSocket, case_id: int):
    """Push live layer.created/updated/deleted events to authenticated case subscribers."""
    token = websocket.query_params.get("token")
    payload = None
    if token:
        try:
            payload = await authorize_case(token, case_id)
        except Exception:
            payload = None
    if not payload or payload.get("user_id") is None or payload.get("email") is None:
        logger.warning(
            "Layer WebSocket authentication rejected | case_id=%s",
            case_id,
        )
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION, reason=WEBSOCKET_AUTH_REQUIRED)
        return

    await layer_connection_manager.connect(case_id, websocket)
    try:
        await websocket.send_json(
            {
                "event": "connection.ready",
                "case_id": case_id,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning(
            "Layer WebSocket closed unexpectedly | case_id=%s | error=%s",
            case_id,
            type(exc).__name__,
        )
    finally:
        layer_connection_manager.disconnect(case_id, websocket)