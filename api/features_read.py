from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.feature_schema import FeatureResponse, FeatureSummaryResponse
from services.feature.feature_service import (
    get_case_features,
    get_feature_by_number,
    get_features,
    get_layer_features,
)
from services.layer.layer_service import get_layer
from utils.constants import FEATURE_NOT_FOUND, LAYER_NOT_FOUND
from utils.dependencies import get_current_user
from utils.exceptions import NotFoundError
from utils.logger import logger

router = APIRouter(tags=["Features"])


# GET ALL FEATURES — any authenticated user
# ===================================================
@router.get("/features", response_model=list[FeatureResponse])
async def list_features(db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /features | user_id={current_user['user_id']}")

    return await get_features(db)


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


