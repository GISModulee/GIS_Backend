import asyncio
import hashlib
import time
from typing import Any

import httpx
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from services.geosearch.utils import (
    MAX_DISCOVERED_PLACES,
    OVERPASS_TIMEOUT_SECONDS,
    OVERPASS_URLS,
    PLACE_CACHE_MAX_ENTRIES,
    PLACE_CACHE_TTL_SECONDS,
    USER_AGENT,
    place_cache,
)
from utils.logger import logger


async def discover_places(geometry: BaseGeometry) -> tuple[list[str], str]:
    query = await _place_query(geometry)
    cache_key = hashlib.sha256(geometry.wkb).hexdigest()
    cached = await _cached_places(cache_key)
    if cached:
        return cached, "cached"

    elements, failure_status = await _fetch_places(query)
    if elements is None:
        cached = await _cached_places(cache_key)
        return (cached, "cached") if cached else ([], failure_status)

    places = await _rank_places(geometry, elements)
    logger.info("Overpass place discovery completed | places=%s", len(places))
    await cache_places(cache_key, places)
    return places, "success" if places else "empty"


async def cache_places(cache_key: str, places: list[str]) -> None:
    if len(place_cache) >= PLACE_CACHE_MAX_ENTRIES:
        oldest_key = min(place_cache, key=lambda key: place_cache[key][0])
        place_cache.pop(oldest_key, None)
    place_cache[cache_key] = (time.monotonic(), list(places))


async def _cached_places(cache_key: str) -> list[str] | None:
    cached = place_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] <= PLACE_CACHE_TTL_SECONDS:
        logger.info("Using cached place discovery | places=%s", len(cached[1]))
        return list(cached[1])
    return None


async def _place_query(geometry: BaseGeometry) -> str:
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    place_types = (
        "city|town|village|hamlet|suburb|quarter|neighbourhood|"
        "locality|isolated_dwelling"
    )
    return (
        "[out:json][timeout:25];"
        f'nwr["place"~"^({place_types})$"]["name"]'
        f"({min_lat},{min_lon},{max_lat},{max_lon});"
        "out center tags;"
    )


async def _fetch_places(query: str) -> tuple[list[dict[str, Any]] | None, str]:
    failure_status = "error"
    elements = None
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(OVERPASS_TIMEOUT_SECONDS, connect=3.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    ) as client:
        tasks = {
            asyncio.create_task(_fetch_endpoint(client, endpoint, query))
            for endpoint in OVERPASS_URLS
        }
        try:
            while tasks and elements is None:
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    endpoint_elements, status = task.result()
                    if endpoint_elements is not None:
                        elements = endpoint_elements
                        break
                    failure_status = status
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    return elements, failure_status


async def _fetch_endpoint(
    client: httpx.AsyncClient, endpoint: str, query: str
) -> tuple[list[dict[str, Any]] | None, str]:
    try:
        response = await client.post(endpoint, data={"data": query})
        if response.status_code == 429:
            logger.warning("Overpass place discovery rate limited | endpoint=%s", endpoint)
            return None, "rate_limited"
        response.raise_for_status()
        return response.json().get("elements", []), "success"
    except httpx.TimeoutException:
        logger.warning("Overpass place discovery timed out | endpoint=%s", endpoint)
        return None, "timeout"
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning(
            "Overpass place discovery failed | endpoint=%s | error=%s",
            endpoint,
            type(exc).__name__,
        )
        return None, "error"


async def _rank_places(geometry: BaseGeometry, elements: list[dict[str, Any]]) -> list[str]:
    candidates = []
    seen = set()
    marker = geometry.representative_point()
    type_priority = {
        "city": 0,
        "town": 1,
        "village": 2,
        "suburb": 3,
        "quarter": 4,
        "neighbourhood": 5,
        "hamlet": 6,
        "locality": 7,
        "isolated_dwelling": 8,
    }
    for element in elements:
        ranked = await _place_candidate(geometry, marker, type_priority, element)
        if ranked and ranked[3].casefold() not in seen:
            seen.add(ranked[3].casefold())
            candidates.append(ranked)
    candidates.sort(key=lambda candidate: candidate[:3])
    return [candidate[3] for candidate in candidates[:MAX_DISCOVERED_PLACES]]


async def _place_candidate(
    geometry: BaseGeometry, marker: Point, type_priority: dict[str, int], element: dict[str, Any]
) -> tuple[float, int, int, str] | None:
    tags = element.get("tags") or {}
    name = str(tags.get("name", "")).strip()
    center = element.get("center") or element
    lat = center.get("lat")
    lon = center.get("lon")
    if not name or lat is None or lon is None:
        return None
    try:
        point = Point(float(lon), float(lat))
    except (TypeError, ValueError):
        return None
    if not geometry.covers(point):
        return None
    try:
        population = int(str(tags.get("population", "0")).replace(",", ""))
    except ValueError:
        population = 0
    return point.distance(marker), type_priority.get(str(tags.get("place", "")), 99), -population, name
