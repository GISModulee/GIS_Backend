from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from utils.logger import logger
from utils.exceptions import NotFoundError
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_WRITE, CAN_DELETE_OPERATIONAL
from schemas.feature_schema import FeatureActionResponse, FeatureCreate, FeatureCreateResponse, FeaturePatch, FeatureResponse

from services.feature_service import (
    create_feature,
    get_features,
    get_feature,
    get_layer_features,
    get_case_features,
    update_feature,
    delete_feature,
    patch_feature
)

router = APIRouter(tags=["Features"])


# ===================================================
# CREATE FEATURE — Admin, Officer, Analyst
# ===================================================
@router.post("/features", response_model=FeatureCreateResponse)
def add_feature(feature: FeatureCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"POST /features | user_id={current_user['user_id']} | role={current_user['role']} | body={feature.model_dump()}")

    return create_feature(feature, db, current_user["user_id"])


# ===================================================
# GET ALL FEATURES — any authenticated user
# ===================================================
@router.get("/features", response_model=list[FeatureResponse])
def list_features(db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /features | user_id={current_user['user_id']}")

    return get_features(db)


# ===================================================
# UPDATE FEATURE (FULL) — Admin, Officer, Analyst
# ===================================================
@router.put("/features/{feature_id}", response_model=FeatureActionResponse)
def edit_feature(feature_id: int, feature: FeatureCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PUT /features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_feature(feature_id, db)

    if existing is None:
        logger.warning(f"Feature not found | feature_id={feature_id}")
        raise NotFoundError("Feature not found")

    return update_feature(feature_id, feature, db)


# ===================================================
# PATCH FEATURE (PARTIAL) — Admin, Officer, Analyst
# ===================================================
@router.patch("/features/{feature_id}", response_model=FeatureActionResponse)
def edit_feature_partial(feature_id: int, feature: FeaturePatch, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PATCH /features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    # FIX (issue #12 in review): every other mutating route in this
    # router does its own existence check before calling the service
    # function; this one used to skip it and rely solely on
    # patch_feature()'s internal check. Functionally equivalent, but
    # now consistent with the rest of the file.
    existing = get_feature(feature_id, db)

    if existing is None:
        logger.warning(f"Feature not found | feature_id={feature_id}")
        raise NotFoundError("Feature not found")

    return patch_feature(feature_id, feature, db)


# ===================================================
# DELETE FEATURE — Admin, Officer
# ===================================================
@router.delete("/features/{feature_id}", response_model=FeatureActionResponse)
def remove_feature(feature_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_DELETE_OPERATIONAL))):

    logger.warning(f"DELETE /features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_feature(feature_id, db)

    if existing is None:
        logger.warning(f"Feature not found | feature_id={feature_id}")
        raise NotFoundError("Feature not found")

    return delete_feature(feature_id, db)


# ===================================================
# GET FEATURES OF A LAYER — any authenticated user
# ===================================================
@router.get("/layers/{layer_id}/features", response_model=list[FeatureResponse])
def list_layer_features(layer_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /layers/{layer_id}/features | user_id={current_user['user_id']}")

    return get_layer_features(layer_id, db)



# ===================================================
# GET FEATURES OF A CASE — any authenticated user
# ===================================================
@router.get("/cases/{case_id}/features", response_model=list[FeatureResponse])
def list_case_features(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    logger.info(
        f"GET /cases/{case_id}/features | user_id={current_user['user_id']}"
    )

    return get_case_features(case_id, db)
