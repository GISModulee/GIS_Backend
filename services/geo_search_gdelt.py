import asyncio
import json
import time
from datetime import datetime
from typing import Any

import httpx
from shapely.geometry.base import BaseGeometry

import services.geo_search_utils as state
from services.geo_search_utils import (
    GDELT_QUERY_TERMS,
    GDELT_TIMEOUT,
    GDELT_URLS,
    USER_AGENT,
    ProviderResult,
    RawNewsItem,
    as_gdelt_datetime,
    is_allowed_domain,
    provider_result,
    raw_item,
    search_query,
)
from utils.constants import (
    GEO_SEARCH_GDELT_FAILED,
    GEO_SEARCH_GDELT_RATE_LIMITED,
    GEO_SEARCH_PROVIDER_EMPTY,
    GEO_SEARCH_PROVIDER_ERROR,
    GEO_SEARCH_PROVIDER_RATE_LIMITED,
    GEO_SEARCH_PROVIDER_TIMEOUT,
    GEO_SEARCH_STATUS_SUCCESS,
)
from utils.logger import logger


async def fetch_gdelt(
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ProviderResult:
    return await fetch_gdelt_batch(
        area_terms[:GDELT_QUERY_TERMS],
        user_terms,
        geometry,
        max_results,
        start_date,
        end_date,
    )


async def fetch_gdelt_batch(
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ProviderResult:
    name = "gdelt"
    params = await gdelt_params(
        await search_query(area_terms, user_terms), max_results, start_date, end_date
    )
    request_key = json.dumps(params, sort_keys=True, default=str)
    task = state.gdelt_inflight.get(request_key)
    if task is None or task.done():
        task = asyncio.create_task(request_gdelt(name, params, geometry))
        state.gdelt_inflight[request_key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done() and state.gdelt_inflight.get(request_key) is task:
            state.gdelt_inflight.pop(request_key, None)


async def gdelt_params(
    query: str,
    max_results: int,
    start_date: datetime | None,
    end_date: datetime | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "mode": "artlist",
        "maxrecords": min(max_results, 250),
        "format": "json",
        "sort": "datedesc",
    }
    if start_date:
        params["startdatetime"] = await as_gdelt_datetime(start_date)
    if end_date:
        params["enddatetime"] = await as_gdelt_datetime(end_date)
    if not start_date and not end_date:
        params["timespan"] = "1month"
    return params


async def wait_for_gdelt_rate_limit() -> None:
    elapsed = time.monotonic() - state.gdelt_last_request_at
    delay = state.GDELT_MIN_INTERVAL_SECONDS - elapsed
    if delay > 0:
        await asyncio.sleep(delay)


async def request_gdelt(
    name: str,
    params: dict[str, Any],
    geometry: BaseGeometry,
    allowed_domains: tuple[str, ...] = (),
) -> ProviderResult:
    last_status = GEO_SEARCH_PROVIDER_ERROR
    async with state.gdelt_request_lock:
        async with httpx.AsyncClient(
            timeout=GDELT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            for endpoint_index, endpoint in enumerate(GDELT_URLS):
                result, retry_status = await _request_endpoint(
                    client, endpoint_index, endpoint, name,
                    params, geometry, allowed_domains)
                if result is not None:
                    return result
                last_status = retry_status
    return await provider_result(
        name,
        last_status,
        detail=GEO_SEARCH_GDELT_FAILED,
    )


async def _request_endpoint(
    client: httpx.AsyncClient,
    endpoint_index: int,
    endpoint: str,
    name: str,
    params: dict[str, Any],
    geometry: BaseGeometry,
    allowed_domains: tuple[str, ...],
) -> tuple[ProviderResult | None, str]:
    await wait_for_gdelt_rate_limit()
    state.gdelt_last_request_at = time.monotonic()
    request_started = time.perf_counter()
    endpoint_label = "https" if endpoint_index == 0 else "http"
    try:
        response = await client.get(endpoint, params=params)
        if response.status_code == 429:
            result = await provider_result(
                name, GEO_SEARCH_PROVIDER_RATE_LIMITED, detail=GEO_SEARCH_GDELT_RATE_LIMITED)
            return result, GEO_SEARCH_PROVIDER_RATE_LIMITED
        response.raise_for_status()
        articles = response.json().get("articles", [])
        items = await _gdelt_items(name, geometry, articles, allowed_domains)
        logger.info(
            "%s request completed | endpoint=%s | results=%s | elapsed=%.3f",
            name,
            endpoint_label,
            len(items),
            time.perf_counter() - request_started,
        )
        status = GEO_SEARCH_STATUS_SUCCESS if items else GEO_SEARCH_PROVIDER_EMPTY
        return await provider_result(name, status, items), GEO_SEARCH_STATUS_SUCCESS
    except httpx.TimeoutException:
        logger.warning("%s request timed out | endpoint=%s", name, endpoint_label)
        return None, GEO_SEARCH_PROVIDER_TIMEOUT
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning(
            "%s request failed | endpoint=%s | error=%s",
            name,
            endpoint_label,
            type(exc).__name__,
        )
        return None, GEO_SEARCH_PROVIDER_ERROR


async def _gdelt_items(
    name: str,
    geometry: BaseGeometry,
    articles: list[dict[str, Any]],
    allowed_domains: tuple[str, ...],
) -> list[RawNewsItem]:
    marker = geometry.representative_point()
    items = []
    for index, article in enumerate(articles):
        url = str(article.get("url", ""))
        if allowed_domains and not await is_allowed_domain(url, allowed_domains):
            continue
        items.append(await raw_item(
            name,
            url or f"{name}-{index}",
            article.get("title", "News article"),
            url,
            article.get("domain", name.title()),
            None,
            article.get("seendate"),
            marker,
        ))
    return items
