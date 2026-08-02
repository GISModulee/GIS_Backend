import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable

from shapely.geometry.base import BaseGeometry

from services.geosearch.utils import (
    PLACE_BATCH_SIZE,
    PROVIDER_CONCURRENCY,
    ProviderResult,
    parse_datetime,
    provider_result,
)
from utils.constants import (
    GEO_SEARCH_BATCHES_FAILED,
    GEO_SEARCH_BATCHES_PARTIAL,
    GEO_SEARCH_PROVIDER_EMPTY,
    GEO_SEARCH_PROVIDER_ERROR,
    GEO_SEARCH_PROVIDER_RATE_LIMITED,
    GEO_SEARCH_PROVIDER_TIMEOUT,
    GEO_SEARCH_STATUS_SUCCESS,
)

BatchFetcher = Callable[
    [list[str], list[str], BaseGeometry, int, datetime | None, datetime | None],
    Awaitable[ProviderResult],
]


async def fetch_in_place_batches(
    fetch_batch: BatchFetcher,
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    concurrency: int | None = None,
) -> ProviderResult:
    batches = [
        area_terms[index:index + PLACE_BATCH_SIZE]
        for index in range(0, len(area_terms), PLACE_BATCH_SIZE)
    ]
    semaphore = asyncio.Semaphore(concurrency or PROVIDER_CONCURRENCY)
    results = await asyncio.gather(*(
        _run_batch(
            semaphore, fetch_batch, batch, user_terms, geometry,
            min(max_results, 20), start_date, end_date,
        )
        for batch in batches
    ))
    items = [item for result in results for item in result.items]
    dated_items = [(await parse_datetime(item.published_at), item) for item in items]
    dated_items.sort(
        key=lambda entry: entry[0] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    items = [item for _, item in dated_items[:max_results]]
    healthy = [
        result for result in results
        if result.status in {GEO_SEARCH_STATUS_SUCCESS, GEO_SEARCH_PROVIDER_EMPTY}
    ]
    if healthy:
        status = GEO_SEARCH_STATUS_SUCCESS if items else GEO_SEARCH_PROVIDER_EMPTY
        detail = None if len(healthy) == len(results) else GEO_SEARCH_BATCHES_PARTIAL
    else:
        statuses = {result.status for result in results}
        status = (
            GEO_SEARCH_PROVIDER_RATE_LIMITED
            if statuses == {GEO_SEARCH_PROVIDER_RATE_LIMITED}
            else GEO_SEARCH_PROVIDER_TIMEOUT
            if statuses == {GEO_SEARCH_PROVIDER_TIMEOUT}
            else GEO_SEARCH_PROVIDER_ERROR
        )
        detail = GEO_SEARCH_BATCHES_FAILED
    return await provider_result(results[0].name, status, items, detail)


async def _run_batch(
    semaphore: asyncio.Semaphore,
    fetch_batch: BatchFetcher,
    batch: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None,
    end_date: datetime | None,
) -> ProviderResult:
    async with semaphore:
        return await fetch_batch(
            batch, user_terms, geometry, max_results, start_date, end_date
        )
