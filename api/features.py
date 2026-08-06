from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from utils.constants import FEATURE_NOT_FOUND, LAYER_NOT_FOUND
from utils.logger import logger
from utils.exceptions import NotFoundError
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_WRITE, CAN_DELETE_OPERATIONAL
from schemas.feature_schema import (
    FeatureActionResponse,
    FeatureCreate,
    FeatureCreateResponse,
    FeaturePatch,
    FeatureResponse,
    FeatureSummaryResponse,
)

from services.feature.feature_service import (
    create_feature,
    get_features,
    get_feature,
    get_feature_by_number, 
    get_layer_features,
    get_case_features,
    update_feature,
    delete_feature,
    patch_feature
)
from services.layer.layer_service import get_layer

router = APIRouter(tags=["Features"])


# ===================================================
# CREATE FEATURE — Admin, Officer, Analyst
# ===================================================
@router.post("/features", response_model=FeatureCreateResponse)
async def add_feature(feature: FeatureCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"POST /features | user_id={current_user['user_id']} | role={current_user['role']} | body={feature.model_dump()}")

    return await create_feature(feature, db, current_user["user_id"])


# ===================================================
# GET ALL FEATURES — any authenticated user
# ===================================================
@router.get("/features", response_model=list[FeatureResponse])
async def list_features(db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /features | user_id={current_user['user_id']}")

    return await get_features(db)


# ===================================================
# UPDATE FEATURE (FULL) — Admin, Officer, Analyst
# ===================================================
@router.put("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def edit_feature(
    case_id: int,
    layer_id: int,
    feature_id: int,
    feature: FeatureCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_WRITE))
):

    logger.info(f"PUT /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    feature.case_id = case_id
    feature.layer_id = layer_id

    return await update_feature(feature_id, feature, db)


# ===================================================
# PATCH FEATURE (PARTIAL) — Admin, Officer, Analyst
# ===================================================
@router.patch("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def edit_feature_partial(
    case_id: int,
    layer_id: int,
    feature_id: int,
    feature: FeaturePatch,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_WRITE))
):

    logger.info(f"PATCH /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    return await patch_feature(feature_id, feature, db)


# ===================================================
# DELETE FEATURE — Admin, Officer
# ===================================================
@router.delete("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def remove_feature(
    case_id: int,
    layer_id: int,
    feature_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_DELETE_OPERATIONAL))
):

    logger.warning(f"DELETE /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    return await delete_feature(feature_id, db)


# ===================================================
# GET SINGLE FEATURE BY NUMBER (scoped to case + layer) — any authenticated user
# ===================================================
@router.get("/cases/{case_id}/layers/{layer_id}/features/{feature_number}", response_model=FeatureResponse)
async def get_single_feature(
    case_id: int,
    layer_id: int,
    feature_number: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    logger.info(f"GET /cases/{case_id}/layers/{layer_id}/features/{feature_number} | user_id={current_user['user_id']}")

    feature = await get_feature_by_number(case_id, layer_id, feature_number, db)

    if not feature:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    return feature

# ===================================================
# GET FEATURES OF A LAYER (scoped to case) — any authenticated user
# ===================================================
@router.get("/cases/{case_id}/layers/{layer_id}/features", response_model=list[FeatureSummaryResponse])
async def list_layer_features(
    case_id: int,
    layer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    logger.info(f"GET /cases/{case_id}/layers/{layer_id}/features | user_id={current_user['user_id']}")

    layer = await get_layer(layer_id, db)

    if not layer or layer["case_id"] != case_id:
        logger.warning(f"Layer not found | case_id={case_id} | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    return await get_layer_features(layer_id, db)



# ===================================================
# GET FEATURES OF A CASE — any authenticated user
# ===================================================
@router.get("/cases/{case_id}/features", response_model=list[FeatureResponse])
async def list_case_features(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    logger.info(
        f"GET /cases/{case_id}/features | user_id={current_user['user_id']}"
    )

    return await get_case_features(case_id, db)
