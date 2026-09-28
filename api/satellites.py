from fastapi import APIRouter, Depends, Query

from schemas.live_data_schema import GeoJSONFeatureCollection
from services.satellite_service import satellite_service
from utils.config import settings
from utils.constants import DEFAULT_SATELLITE_GROUP, STATUS_OK, SatelliteGroup
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
    group: SatelliteGroup = Query(
        default=DEFAULT_SATELLITE_GROUP,
        description=(
            "CelesTrak element group to read. 'stations' is crewed space "
            "stations, 'visual' the brightest objects, 'weather' weather "
            "satellites, 'gps-ops' the GPS constellation, 'starlink' the "
            "Starlink constellation. Omitting it returns the full active "
            "catalog."
        ),
    ),
) -> GeoJSONFeatureCollection:
    """Return token-protected CelesTrak TLE satellite positions propagated with SGP4."""
    return await satellite_service.geojson(bbox=bbox, limit=limit, group=group)
