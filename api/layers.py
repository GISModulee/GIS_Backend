from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.layer_schema import LayerActionResponse, LayerCreate, LayerCreateResponse, LayerPatch, LayerResponse
from utils.exceptions import NotFoundError
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_WRITE, CAN_DELETE_OPERATIONAL
from services.layer_service import (
    create_layer,
    get_layers,
    get_layer,
    update_layer,
    delete_layer,
    get_case_layers,
    patch_layer
)

from utils.logger import logger

router = APIRouter(
    prefix="/layers",
    tags=["Layers"]
)

@router.post("", response_model=LayerCreateResponse)
def add_layer(layer: LayerCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):
    logger.info(f"POST /layers | user_id={current_user['user_id']} | role={current_user['role']} | body={layer.model_dump()}")
    return create_layer(layer.model_dump(), db)


@router.get("", response_model=list[LayerResponse])
def list_layers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    logger.info(f"GET /layers | user_id={current_user['user_id']}")
    return get_layers(db)


@router.get("/{layer_id}", response_model=LayerResponse)
def get_single_layer(layer_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /layers/{layer_id} | user_id={current_user['user_id']}")

    layer = get_layer(layer_id, db)

    if not layer:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    return layer


@router.put("/{layer_id}", response_model=LayerActionResponse)
def edit_layer(layer_id: int, layer: LayerCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PUT /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_layer(layer_id, db)

    if not existing:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    return update_layer(layer_id, layer.model_dump(), db)


@router.patch("/{layer_id}", response_model=LayerActionResponse)
def edit_layer_partial(layer_id: int, layer: LayerPatch, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PATCH /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_layer(layer_id, db)

    if not existing:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    return patch_layer(layer_id, layer.model_dump(exclude_unset=True), db)


# ===================================================
# DELETE LAYER — Admin, Officer
# ===================================================
@router.delete("/{layer_id}", response_model=LayerActionResponse)
def remove_layer(layer_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_DELETE_OPERATIONAL))):

    logger.warning(f"DELETE /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_layer(layer_id, db)

    if not existing:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    return delete_layer(layer_id, db)


# ===================================================
# GET LAYERS BY CASE — any authenticated user
# ===================================================
@router.get("/case/{case_id}", response_model=list[LayerResponse])
def list_case_layers(case_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /layers/case/{case_id} | user_id={current_user['user_id']}")

    return get_case_layers(case_id, db)
