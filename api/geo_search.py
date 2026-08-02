from fastapi import APIRouter, Depends, status

from schemas.geo_search_schema import GeoSearchRequest, GeoSearchResponse
from services.geo_search_service import GeoSearchService
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
    status_code=status.HTTP_200_OK,
)
async def search_news(request: GeoSearchRequest) -> GeoSearchResponse:
    """Search current news relevant to a supplied geographic area."""
    logger.info(
        "Geo news search requested | case_id=%s | layer_id=%s | "
        "feature_number=%s | max_results=%s",
        request.case_id,
        request.layer_id,
        request.feature_number,
        request.max_results,
    )
    return await GeoSearchService.execute_news_search(request)
