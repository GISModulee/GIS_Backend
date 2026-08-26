from fastapi import APIRouter, Depends, Query

from schemas.comment_schema import CommentCreateResponse
from schemas.geo_search_schema import (
    GeoNewsSearchHistoryClearResponse,
    GeoNewsSearchHistoryItem,
    GeoSearchRequest,
    GeoSearchResponse,
    NewsCommentRequest,
)
from services.geosearch.history import (
    clear_news_search_history,
    get_news_search_history,
    save_news_search_history,
)
from services.geosearch.news_comments import add_news_to_comment
from services.geosearch.service import GeoSearchService
from utils.constants import STATUS_OK
from utils.dependencies import get_current_user, require_roles
from utils.logger import logger
from utils.roles import CAN_COMMENT


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
async def search_news(
    request: GeoSearchRequest,
    current_user=Depends(get_current_user),
) -> GeoSearchResponse:
    """Search current news relevant to a supplied geographic area."""
    logger.info(
        "Geo news search requested | case_id=%s | layer_id=%s | "
        "feature_number=%s | max_results=%s",
        request.case_id,
        request.layer_id,
        request.feature_number,
        request.max_results,
    )
    response = await GeoSearchService.execute_news_search(request)
    await save_news_search_history(request, current_user["user_id"])
    return response


@router.get(
    "/news/history",
    response_model=list[GeoNewsSearchHistoryItem],
    status_code=STATUS_OK,
)
async def list_news_search_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
):
    logger.info(
        "News search history requested | user_id=%s | limit=%s | offset=%s",
        current_user["user_id"],
        limit,
        offset,
    )
    return await get_news_search_history(current_user["user_id"], limit, offset)


@router.delete(
    "/news/history",
    response_model=GeoNewsSearchHistoryClearResponse,
    status_code=STATUS_OK,
)
async def clear_news_history(current_user=Depends(get_current_user)):
    logger.info("Clear news search history requested | user_id=%s", current_user["user_id"])
    return await clear_news_search_history(current_user["user_id"])


@router.post(
    "/news/comment",
    response_model=CommentCreateResponse,
    status_code=STATUS_OK,
)
async def add_news_comment(
    request: NewsCommentRequest,
    current_user=Depends(require_roles(CAN_COMMENT)),
):
    """Store a selected news item as a normal feature comment."""
    logger.info(
        "Add news to comment requested | user_id=%s | case_id=%s | layer_id=%s | feature_number=%s",
        current_user["user_id"],
        request.case_id,
        request.layer_id,
        request.feature_number,
    )
    return await add_news_to_comment(request, current_user)
