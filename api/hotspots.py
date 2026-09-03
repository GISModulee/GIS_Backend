from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.hotspot_schema import HotspotSaveRequest, HotspotSaveResponse, HotspotSearchRequest, HotspotSearchResponse
from services.feature.feature_service import get_feature
from services.feature.feature_websocket_manager import feature_connection_manager
from services.hotspots.service import save_hotspots, search_hotspots
from utils.constants import STATUS_OK
from utils.dependencies import get_current_user, require_roles
from utils.logger import logger
from utils.roles import CAN_WRITE


router = APIRouter(
    prefix="/hotspots",
    tags=["Hotspots"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/search", response_model=HotspotSearchResponse, status_code=STATUS_OK)
async def search_feature_hotspots(
    request: HotspotSearchRequest,
    db: Session = Depends(get_db),
):
    logger.info(
        "Hotspot search requested | case_id=%s | layer_id=%s | feature_number=%s | limit=%s",
        request.case_id,
        request.layer_id,
        request.feature_number,
        request.limit,
    )
    return await search_hotspots(request, db)


@router.post("/save", response_model=HotspotSaveResponse, status_code=STATUS_OK)
async def save_feature_hotspots(
    request: HotspotSaveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(CAN_WRITE)),
):
    logger.info(
        "Hotspot save requested | user_id=%s | case_id=%s | source_layer_id=%s | "
        "source_feature_number=%s | count=%s",
        current_user["user_id"],
        request.case_id,
        request.source_layer_id,
        request.source_feature_number,
        len(request.hotspots),
    )
    result = await save_hotspots(request, db, current_user)
    for feature_id in result.get("feature_ids", []):
        created_feature = await get_feature(feature_id, db)
        if created_feature is None:
            continue
        await feature_connection_manager.broadcast(
            request.case_id,
            {
                "event": "feature.created",
                "case_id": request.case_id,
                "layer_id": result["layer_id"],
                "feature": created_feature,
            },
        )
    return result
