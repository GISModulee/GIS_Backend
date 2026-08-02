from fastapi import APIRouter, Depends

from schemas.geo_search_schema import GeoSearchRequest, GeoSearchResponse
from services.geosearch.service import GeoSearchService
from utils.constants import STATUS_OK
from utils.dependencies import get_current_user
from utils.logger import logger


router = APIRouter(
    prefix="/geo-search",
    tags=["Geo Search"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/news",
    response_model=GeoSearchResponse,
    status_code=STATUS_OK,
)
async def search_news(request: GeoSearchRequest) -> GeoSearchResponse:
    """Search current news relevant to a supplied geographic area."""
    logger.info(
        "Geo news search requested | case_id=%s | layer_id=%s | "
        "feature_id=%s | max_results=%s",
        request.case_id,
        request.layer_id,
        request.feature_id,
        request.max_results,
    )
    return await GeoSearchService.execute_news_search(request)
