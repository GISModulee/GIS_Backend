from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.layer_schema import LayerActionResponse, LayerCreate, LayerCreateResponse, LayerPatch, LayerResponse
from utils.constants import LAYER_NOT_FOUND
from utils.exceptions import NotFoundError
from utils.dependencies import get_current_user, require_roles
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

from utils.logger import logger

router = APIRouter(
    prefix="/layers",
    tags=["Layers"],
)


@router.post("", response_model=LayerCreateResponse)
async def add_layer(layer: LayerCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):
    logger.info(f"POST /layers | user_id={current_user['user_id']} | role={current_user['role']} | body={layer.model_dump()}")
    return await create_layer(layer.model_dump(), db)


@router.get("", response_model=list[LayerResponse])
async def list_layers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    logger.info(f"GET /layers | user_id={current_user['user_id']}")
    return await get_layers(db)


@router.get("/case/{case_id}", response_model=list[LayerResponse])
async def list_case_layers(case_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    logger.info(f"GET /layers/case/{case_id} | user_id={current_user['user_id']}")
    return await get_case_layers(case_id, db)


@router.get("/case/{case_id}/{layer_id}", response_model=LayerResponse)
async def get_single_layer(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
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
    current_user=Depends(require_roles(CAN_WRITE))
):
    logger.info(f"PUT /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    return await update_layer(layer_id, layer.model_dump(), db)


@router.patch("/case/{case_id}/{layer_id}", response_model=LayerActionResponse)
async def edit_layer_partial(
    case_id: int,
    layer_id: int,
    layer: LayerPatch,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_WRITE))
):
    logger.info(f"PATCH /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    return await patch_layer(layer_id, layer.model_dump(exclude_unset=True), db)


@router.delete("/case/{case_id}/{layer_id}", response_model=LayerActionResponse)
async def remove_layer(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_DELETE_OPERATIONAL))
):
    logger.warning(f"DELETE /layers/case/{case_id}/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_layer(layer_id, db)

    if not existing or existing["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    return await delete_layer(layer_id, db)
