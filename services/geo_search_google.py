import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote, urlparse

import httpx
from shapely.geometry.base import BaseGeometry

import services.geo_search_utils as state
from services.geo_search_batches import fetch_in_place_batches
from services.geo_search_utils import (
    GDELT_QUERY_TERMS,
    REQUEST_TIMEOUT,
    USER_AGENT,
    ProviderResult,
    as_utc,
    google_date_query,
    is_allowed_domain,
    parse_datetime,
    provider_result,
    raw_item,
    search_query,
)
from utils.constants import (
    GEO_SEARCH_GOVERNMENT_TIMEOUT,
    GEO_SEARCH_PROVIDER_EMPTY,
    GEO_SEARCH_PROVIDER_ERROR,
    GEO_SEARCH_PROVIDER_RATE_LIMITED,
    GEO_SEARCH_PROVIDER_TIMEOUT,
    GEO_SEARCH_STATUS_SUCCESS,
)
from utils.logger import logger


async def fetch_google_news(
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ProviderResult:
    return await fetch_in_place_batches(
        fetch_google_news_batch,
        area_terms,
        user_terms,
        geometry,
        max_results,
        start_date,
        end_date,
    )


async def fetch_google_news_batch(
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ProviderResult:
    name = "google_news"
    query = " ".join(filter(None, (
        await search_query(area_terms, user_terms),
        await google_date_query(start_date, end_date),
    )))
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await google_get(client, url)
        if response.status_code == 429:
            return await provider_result(name, GEO_SEARCH_PROVIDER_RATE_LIMITED)
        response.raise_for_status()
        return await _google_rss_result(name, response.content, geometry, max_results)
    except httpx.TimeoutException:
        return await provider_result(name, GEO_SEARCH_PROVIDER_TIMEOUT)
    except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
        logger.warning("Google News request failed | error=%s", type(exc).__name__)
        return await provider_result(
            name, GEO_SEARCH_PROVIDER_ERROR, detail=type(exc).__name__
        )


async def fetch_government_news(
    area_terms: list[str],
    user_terms: list[str],
    geometry: BaseGeometry,
    max_results: int,
    domains: tuple[str, ...],
    start_date: datetime | None,
    end_date: datetime | None,
) -> ProviderResult:
    name = "government"
    domain_query = " OR ".join(f"site:{domain}" for domain in domains)
    query = (
        f"{await search_query(area_terms[:GDELT_QUERY_TERMS], user_terms)} "
        f"({domain_query}) {await google_date_query(start_date, end_date)}"
    ).strip()
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await google_get(client, url)
        if response.status_code == 429:
            return await provider_result(name, GEO_SEARCH_PROVIDER_RATE_LIMITED)
        response.raise_for_status()
        return await _government_rss_result(
            name, response.content, geometry, max_results, domains, start_date, end_date
        )
    except httpx.TimeoutException:
        return await provider_result(
            name, GEO_SEARCH_PROVIDER_TIMEOUT, detail=GEO_SEARCH_GOVERNMENT_TIMEOUT
        )
    except (httpx.HTTPError, ET.ParseError, ValueError, TypeError) as exc:
        logger.warning("Government search failed | error=%s", type(exc).__name__)
        return await provider_result(
            name, GEO_SEARCH_PROVIDER_ERROR, detail=type(exc).__name__
        )


async def google_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    async with state.google_request_lock:
        elapsed = time.monotonic() - state.google_last_request_at
        delay = state.GOOGLE_MIN_INTERVAL_SECONDS - elapsed
        if delay > 0:
            await asyncio.sleep(delay)
        state.google_last_request_at = time.monotonic()
        return await client.get(url)


async def _google_rss_result(
    name: str, content: bytes, geometry: BaseGeometry, max_results: int
) -> ProviderResult:
    marker = geometry.representative_point()
    root = ET.fromstring(content)
    items = []
    for index, entry in enumerate(root.findall(".//item")[: max_results * 2]):
        link = (entry.findtext("link") or "").strip()
        title = (entry.findtext("title") or "News update").strip()
        source_node = entry.find("source")
        source = (
            source_node.text.strip()
            if source_node is not None and source_node.text
            else "Google News"
        )
        items.append(await raw_item(
            name, link or f"google-{index}", title, link, source,
            entry.findtext("description"), entry.findtext("pubDate"), marker,
        ))
    status = GEO_SEARCH_STATUS_SUCCESS if items else GEO_SEARCH_PROVIDER_EMPTY
    return await provider_result(name, status, items)


async def _government_rss_result(
    name: str, content: bytes, geometry: BaseGeometry, max_results: int,
    domains: tuple[str, ...], start_date: datetime | None, end_date: datetime | None,
) -> ProviderResult:
    marker = geometry.representative_point()
    root = ET.fromstring(content)
    items = []
    for index, entry in enumerate(root.findall(".//item")[: max_results * 3]):
        source_node = entry.find("source")
        source_url = source_node.attrib.get("url", "") if source_node is not None else ""
        if not await is_allowed_domain(source_url, domains):
            continue
        published_at = entry.findtext("pubDate")
        published = await parse_datetime(published_at)
        if start_date and (not published or published < await as_utc(start_date)):
            continue
        if end_date and (not published or published > await as_utc(end_date)):
            continue
        link = (entry.findtext("link") or "").strip()
        source = (
            source_node.text.strip()
            if source_node is not None and source_node.text
            else urlparse(source_url).hostname or "Government"
        )
        items.append(await raw_item(
            name, link or f"government-{index}",
            (entry.findtext("title") or "Government update").strip(),
            link, source, entry.findtext("description"), published_at, marker,
        ))
    status = GEO_SEARCH_STATUS_SUCCESS if items else GEO_SEARCH_PROVIDER_EMPTY
    return await provider_result(name, status, items[:max_results])
