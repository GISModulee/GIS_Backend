from fastapi import APIRouter, Depends, Query

from schemas.live_data_schema import GeoJSONFeatureCollection
from services.aircraft_service import aircraft_service
from utils.constants import STATUS_OK
from utils.dependencies import get_current_user


router = APIRouter(
    prefix="/api/aircraft",
    tags=["Live Aircraft"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=GeoJSONFeatureCollection,
    status_code=STATUS_OK,
    summary="List live aircraft positions",
)
async def list_aircraft(
    lamin: float | None = Query(default=None, description="Lower latitude bound for OpenSky WGS84 bbox"),
    lomin: float | None = Query(default=None, description="Lower longitude bound for OpenSky WGS84 bbox"),
    lamax: float | None = Query(default=None, description="Upper latitude bound for OpenSky WGS84 bbox"),
    lomax: float | None = Query(default=None, description="Upper longitude bound for OpenSky WGS84 bbox"),
) -> GeoJSONFeatureCollection:
    """Return token-protected live OpenSky aircraft state vectors as GeoJSON."""
    return await aircraft_service.geojson(lamin=lamin, lomin=lomin, lamax=lamax, lomax=lomax)
