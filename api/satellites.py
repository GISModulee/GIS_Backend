from fastapi import APIRouter, Depends, Query

from schemas.live_data_schema import GeoJSONFeatureCollection
from services.satellite_service import satellite_service
from utils.config import settings
from utils.constants import STATUS_OK
from utils.dependencies import get_current_user


router = APIRouter(
    prefix="/api/satellites",
    tags=["Live Satellites"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=GeoJSONFeatureCollection,
    status_code=STATUS_OK,
    summary="List current satellite positions",
)
async def list_satellites(
    bbox: str | None = Query(
        default=None,
        description="Optional post-propagation bbox filter: minLon,minLat,maxLon,maxLat",
    ),
    limit: int = Query(default=500, ge=1, le=settings.SATELLITE_MAX_RESULTS),
) -> GeoJSONFeatureCollection:
    """Return token-protected CelesTrak TLE satellite positions propagated with SGP4."""
    return await satellite_service.geojson(bbox=bbox, limit=limit)
