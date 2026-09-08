from __future__ import annotations

from datetime import timezone

from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from schemas.geo_search_schema import NewsCommentRequest
from services.comment.comment_service import create_comment
from services.comment.comment_websocket_manager import comment_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager
from utils.logger import logger


TITLE_LIMIT = 120
SUMMARY_LIMIT = 180


def _truncate(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return f"{value[:limit - 3].rstrip()}..."


def _format_date(request: NewsCommentRequest) -> str | None:
    if request.published_at is None:
        return None
    published = request.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published.strftime("%d %b %Y")


def format_news_comment(request: NewsCommentRequest) -> str:
    lines = [
        "[News]",
        f"Title: {_truncate(request.title, TITLE_LIMIT)}",
        f"Source: {request.source}",
    ]

    published = _format_date(request)
    if published:
        lines.append(f"Published: {published}")

    lines.append(f"URL: {request.url}")

    if request.summary:
        lines.append(f"Summary: {_truncate(request.summary, SUMMARY_LIMIT)}")

    return "\n".join(lines)


async def add_news_to_comment(request: NewsCommentRequest, current_user: dict) -> dict:
    logger.info(
        "Adding news item to feature comments | user_id=%s | case_id=%s | layer_id=%s | feature_number=%s",
        current_user["user_id"],
        request.case_id,
        request.layer_id,
        request.feature_number,
    )

    result = await run_in_threadpool(
        create_comment,
        request.case_id,
        request.layer_id,
        request.feature_number,
        current_user["user_id"],
        format_news_comment(request),
        None,
        None,
        current_user,
    )

    await comment_connection_manager.broadcast(
        request.case_id,
        request.feature_number,
        jsonable_encoder(
            {
                "event": "comment.created",
                "case_id": request.case_id,
                "layer_id": request.layer_id,
                "feature_number": request.feature_number,
                "comment": result["comment"],
                "source": "geo_news",
            }
        ),
    )
    await feature_connection_manager.broadcast(
        request.case_id,
        {
            "event": "feature.comment_created",
            "case_id": request.case_id,
            "layer_id": request.layer_id,
            "feature_number": request.feature_number,
            "comment_id": result["comment"]["id"],
            "has_comments": True,
            "source": "geo_news",
        },
    )

    return {
        **result,
        "message": "News item added to comments successfully",
    }
