from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from models.model import Feature, GeoNewsSearchHistory
from schemas.geo_search_schema import GeoNewsSearchHistoryItem, GeoSearchRequest
from utils.exceptions import ServiceUnavailableError
from utils.logger import logger


NEWS_HISTORY_FAILED = "Failed to update news search history"
NEWS_HISTORY_FETCH_FAILED = "Failed to fetch news search history"
NEWS_HISTORY_CLEAR_FAILED = "Failed to clear news search history"


async def _history_item(record: GeoNewsSearchHistory) -> GeoNewsSearchHistoryItem:
    return GeoNewsSearchHistoryItem(
        id=record.id,
        case_id=record.case_id,
        layer_id=record.layer_id,
        feature_number=record.feature_number,
        feature_name=record.feature_name,
        keywords=record.keywords or [],
        start_date=record.start_date,
        end_date=record.end_date,
        max_results=record.max_results,
        created_at=record.created_at,
    )


async def _feature_name(db, request: GeoSearchRequest) -> str:
    name = db.scalar(
        select(Feature.name).where(
            Feature.case_id == request.case_id,
            Feature.layer_id == request.layer_id,
            Feature.feature_number == request.feature_number,
        )
    )
    name = (name or "").strip()
    return name or f"Feature {request.feature_number}"


async def save_news_search_history(request: GeoSearchRequest, user_id: int) -> None:
    try:
        with SessionLocal.begin() as db:
            db.add(
                GeoNewsSearchHistory(
                    user_id=user_id,
                    case_id=request.case_id,
                    layer_id=request.layer_id,
                    feature_number=request.feature_number,
                    feature_name=await _feature_name(db, request),
                    keywords=list(request.keywords),
                    start_date=request.start_date,
                    end_date=request.end_date,
                    max_results=request.max_results,
                )
            )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to save news search history | user_id=%s | case_id=%s | layer_id=%s | feature_number=%s | error=%s",
            user_id,
            request.case_id,
            request.layer_id,
            request.feature_number,
            exc,
            exc_info=True,
        )
        return


async def get_news_search_history(user_id: int, limit: int = 20, offset: int = 0) -> list[GeoNewsSearchHistoryItem]:
    try:
        with SessionLocal() as db:
            records = db.scalars(
                select(GeoNewsSearchHistory)
                .where(GeoNewsSearchHistory.user_id == user_id)
                .order_by(GeoNewsSearchHistory.created_at.desc(), GeoNewsSearchHistory.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [await _history_item(record) for record in records]
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch news search history | user_id=%s | error=%s",
            user_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(NEWS_HISTORY_FETCH_FAILED) from exc


async def clear_news_search_history(user_id: int) -> dict:
    try:
        with SessionLocal.begin() as db:
            result = db.execute(
                delete(GeoNewsSearchHistory).where(GeoNewsSearchHistory.user_id == user_id)
            )
            deleted_count = result.rowcount or 0
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": "News search history cleared successfully",
        }
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to clear news search history | user_id=%s | error=%s",
            user_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(NEWS_HISTORY_CLEAR_FAILED) from exc
