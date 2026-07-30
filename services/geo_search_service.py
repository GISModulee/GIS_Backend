import asyncio
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlparse

import h3
import httpx
from shapely.geometry import Point, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from database.database import SessionLocal
from models.model import Feature
from schemas.geo_search_schema import (
    GeoSearchRequest,
    GeoSearchResponse,
    NewsItem,
    SourceStatus,
)
from utils.exceptions import (
    BadRequestError,
    GatewayTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from utils.logger import logger


class GeoSearchService:
    """Build and execute a bounded, live, news-only geographic search."""

    USER_AGENT = "GeoIntelligence-GeoSearch/2.1 (news-search)"
    REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
    GDELT_TIMEOUT = httpx.Timeout(15.0, connect=3.0)
    GDELT_URLS = (
        "https://api.gdeltproject.org/api/v2/doc/doc",
        "http://api.gdeltproject.org/api/v2/doc/doc",
    )
    GDELT_MIN_INTERVAL_SECONDS = 5.1
    _gdelt_request_lock = asyncio.Lock()
    _gdelt_last_request_at = 0.0
    _gdelt_inflight: dict[str, asyncio.Task] = {}
    GOOGLE_MIN_INTERVAL_SECONDS = 0.75
    _google_request_lock = asyncio.Lock()
    _google_last_request_at = 0.0
    MAX_AREA_SQUARE_DEGREES = 100.0
    OVERPASS_URLS = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    )
    OVERPASS_TIMEOUT_SECONDS = 6.0
    PLACE_CACHE_TTL_SECONDS = 3600.0
    PLACE_CACHE_MAX_ENTRIES = 256
    MAX_DISCOVERED_PLACES = 24
    PROVIDER_CANDIDATE_LIMIT = 50
    _place_cache: dict[str, tuple[float, list[str]]] = {}
    PLACE_BATCH_SIZE = 15
    PROVIDER_CONCURRENCY = 2
    GDELT_QUERY_TERMS = 8
    GOVERNMENT_DOMAINS = {
        "india": ("gov.in", "nic.in"),
        "united states": ("gov",),
        "united kingdom": ("gov.uk",),
        "australia": ("gov.au",),
        "canada": ("canada.ca", "gc.ca"),
        "new zealand": ("govt.nz",),
    }

    @classmethod
    async def execute_news_search(
        cls, request: GeoSearchRequest
    ) -> GeoSearchResponse:
        started_at = time.perf_counter()
        geometry = await run_in_threadpool(cls._feature_geometry, request.feature_id)
        h3_cells = cls._h3_cells(geometry, request.h3_resolution)
        area, place_result = await asyncio.gather(
            cls._area_context(geometry),
            cls._discover_places(geometry),
        )
        places, discovery_status = place_result
        places = places[: cls.MAX_DISCOVERED_PLACES]
        effective_start = request.start_date
        effective_end = cls._inclusive_end_date(request.end_date)
        primary_terms = area["primary_terms"]
        context_terms = area["context_terms"]
        search_terms = list(dict.fromkeys(primary_terms + places))
        provider_terms = request.keywords + context_terms[:1]
        area["searched_places"] = search_terms
        area["searched_places_count"] = len(search_terms)
        area["place_discovery_status"] = discovery_status

        government_domains = cls._government_domains(area.get("country", ""))
        candidate_limit = cls.PROVIDER_CANDIDATE_LIMIT
        provider_calls = [
            cls._fetch_google_news(
                search_terms, provider_terms, geometry, candidate_limit,
                effective_start, effective_end,
            ),
            cls._fetch_gdelt(
                search_terms, provider_terms, geometry, candidate_limit,
                effective_start, effective_end,
            ),
        ]
        if government_domains:
            provider_calls.append(
                cls._fetch_government_news(
                    search_terms, provider_terms, geometry, candidate_limit,
                    government_domains, effective_start, effective_end,
                )
            )
        provider_results = await asyncio.gather(*provider_calls)

        items = [item for result in provider_results for item in result["items"]]
        items = cls._rank_filter_and_deduplicate(
            items=items,
            geometry=geometry,
            primary_area_terms=primary_terms,
            discovered_area_terms=places,
            context_terms=context_terms,
            query_is_geographically_constrained=bool(context_terms and search_terms),
            user_terms=request.keywords,
            start_date=effective_start,
            end_date=effective_end,
        )
        items.sort(
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        items = items[: request.max_results]

        if not items:
            statuses = {result["status"] for result in provider_results}
            healthy_results = [
                result for result in provider_results
                if result["status"] in {"success", "empty"}
            ]
            logger.warning(
                "Geo news search produced no usable results | providers=%s",
                {
                    result["name"]: {
                        "status": result["status"],
                        "results": len(result["items"]),
                        "detail": result.get("detail"),
                    }
                    for result in provider_results
                },
            )
            if not healthy_results and "timeout" in statuses:
                raise GatewayTimeoutError(
                    "News search timed out before results could be retrieved. Please try again."
                )
            if healthy_results:
                raise NotFoundError(
                    "No matching news was found for the selected area and filters."
                )
            raise ServiceUnavailableError(
                "News providers are temporarily unavailable. Please try again."
            )

        sources: dict[str, SourceStatus] = {}
        for result in provider_results:
            sources[result["name"]] = SourceStatus(
                status=result["status"],
                results=len(result["items"]),
                accepted_results=sum(item.provider == result["name"] for item in items),
                detail=result.get("detail"),
            )

        healthy = sum(result["status"] in {"success", "empty"} for result in provider_results)
        aggregate_status = (
            "success"
            if healthy == len(provider_results)
            else "partial_success"
            if healthy
            else "upstream_unavailable"
        )
        logger.info(
            "Geo news search completed | status=%s | results=%s | elapsed=%.3f",
            aggregate_status,
            len(items),
            time.perf_counter() - started_at,
        )
        return GeoSearchResponse(
            status=aggregate_status,
            total_results=len(items),
            h3_cells_count=len(h3_cells),
            execution_time_seconds=round(time.perf_counter() - started_at, 3),
            area=area,
            sources=sources,
            items=items,
        )

    @classmethod
    def _feature_geometry(cls, feature_id: int) -> BaseGeometry:
        """Load a saved PostGIS feature and return its validated Shapely geometry."""
        logger.info("Loading Geo Search feature | feature_id=%s", feature_id)
        try:
            with SessionLocal() as db:
                row = db.execute(
                    select(
                        Feature.id,
                        func.ST_AsGeoJSON(Feature.geom).label("geometry"),
                    ).where(Feature.id == feature_id)
                ).one_or_none()
        except SQLAlchemyError as exc:
            logger.error(
                "Failed to load Geo Search feature | feature_id=%s | error=%s",
                feature_id,
                exc,
                exc_info=True,
            )
            raise ServiceUnavailableError("Failed to load selected feature") from exc

        if row is None:
            raise NotFoundError("Feature not found")
        if not row.geometry:
            raise UnprocessableEntityError("Selected feature has no geometry")

        try:
            geometry = shape(json.loads(row.geometry))
        except (TypeError, ValueError) as exc:
            logger.error(
                "Stored feature geometry is invalid | feature_id=%s",
                feature_id,
                exc_info=True,
            )
            raise UnprocessableEntityError("Selected feature has invalid geometry") from exc

        return cls._validate_geometry(geometry)

    @classmethod
    def _validate_geometry(cls, geometry: BaseGeometry) -> BaseGeometry:
        if geometry.is_empty:
            raise UnprocessableEntityError("Selected feature has an empty geometry")
        if not geometry.is_valid:
            raise UnprocessableEntityError(
                f"Selected feature has invalid geometry: {explain_validity(geometry)}"
            )
        min_lon, min_lat, max_lon, max_lat = geometry.bounds
        if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
            raise UnprocessableEntityError(
                "Selected feature geometry is outside valid longitude/latitude bounds"
            )
        if (max_lon - min_lon) * (max_lat - min_lat) > cls.MAX_AREA_SQUARE_DEGREES:
            raise BadRequestError("Search area is too large; submit a smaller geometry.")
        return geometry

    @staticmethod
    def _h3_cells(geometry: BaseGeometry, resolution: int) -> list[str]:
        try:
            return sorted(h3.geo_to_cells(mapping(geometry), resolution))
        except Exception as exc:
            logger.warning("H3 coverage failed | error=%s", exc)
            return []

    @classmethod
    async def _discover_places(
        cls, geometry: BaseGeometry
    ) -> tuple[list[str], str]:
        """Return every named OSM place whose point or center lies in the geometry."""
        min_lon, min_lat, max_lon, max_lat = geometry.bounds
        place_types = (
            "city|town|village|hamlet|suburb|quarter|neighbourhood|"
            "locality|isolated_dwelling"
        )
        query = (
            "[out:json][timeout:25];"
            f'nwr["place"~"^({place_types})$"]["name"]'
            f"({min_lat},{min_lon},{max_lat},{max_lon});"
            "out center tags;"
        )
        cache_key = hashlib.sha256(geometry.wkb).hexdigest()
        cached = cls._place_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] <= cls.PLACE_CACHE_TTL_SECONDS:
            logger.info("Using cached place discovery | places=%s", len(cached[1]))
            return list(cached[1]), "cached"

        failure_status = "error"
        elements = None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(cls.OVERPASS_TIMEOUT_SECONDS, connect=3.0),
            headers={"User-Agent": cls.USER_AGENT},
            follow_redirects=False,
        ) as client:
            async def fetch_endpoint(endpoint):
                try:
                    response = await client.post(endpoint, data={"data": query})
                    if response.status_code == 429:
                        logger.warning(
                            "Overpass place discovery rate limited | endpoint=%s",
                            endpoint,
                        )
                        return None, "rate_limited"
                    response.raise_for_status()
                    return response.json().get("elements", []), "success"
                except httpx.TimeoutException:
                    logger.warning(
                        "Overpass place discovery timed out | endpoint=%s", endpoint
                    )
                    return None, "timeout"
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    logger.warning(
                        "Overpass place discovery failed | endpoint=%s | error=%s",
                        endpoint,
                        type(exc).__name__,
                    )
                    return None, "error"

            tasks = {
                asyncio.create_task(fetch_endpoint(endpoint))
                for endpoint in cls.OVERPASS_URLS
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

        if elements is None:
            cached = cls._place_cache.get(cache_key)
            if cached and time.monotonic() - cached[0] <= cls.PLACE_CACHE_TTL_SECONDS:
                logger.info(
                    "Using cached place discovery | places=%s", len(cached[1])
                )
                return list(cached[1]), "cached"
            return [], failure_status

        place_candidates = []
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
            tags = element.get("tags") or {}
            name = str(tags.get("name", "")).strip()
            center = element.get("center") or element
            lat = center.get("lat")
            lon = center.get("lon")
            if not name or lat is None or lon is None:
                continue
            try:
                point = Point(float(lon), float(lat))
            except (TypeError, ValueError):
                continue
            key = name.casefold()
            if geometry.covers(point) and key not in seen:
                seen.add(key)
                place_type = str(tags.get("place", ""))
                try:
                    population = int(str(tags.get("population", "0")).replace(",", ""))
                except ValueError:
                    population = 0
                place_candidates.append((
                    point.distance(marker),
                    type_priority.get(place_type, 99),
                    -population,
                    name,
                ))

        place_candidates.sort(key=lambda candidate: candidate[:3])
        places = [
            candidate[3]
            for candidate in place_candidates[: cls.MAX_DISCOVERED_PLACES]
        ]

        logger.info(
            "Overpass place discovery completed | places=%s",
            len(places),
        )
        cls._cache_places(cache_key, places)
        return places, "success" if places else "empty"

    @classmethod
    def _cache_places(cls, cache_key: str, places: list[str]) -> None:
        if len(cls._place_cache) >= cls.PLACE_CACHE_MAX_ENTRIES:
            oldest_key = min(
                cls._place_cache, key=lambda key: cls._place_cache[key][0]
            )
            cls._place_cache.pop(oldest_key, None)
        cls._place_cache[cache_key] = (time.monotonic(), list(places))

    @classmethod
    async def _area_context(cls, geometry: BaseGeometry) -> dict[str, Any]:
        marker = geometry.representative_point()
        fallback = f"{marker.y:.4f},{marker.x:.4f}"
        address: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": marker.y, "lon": marker.x, "format": "jsonv2", "addressdetails": 1},
                )
                response.raise_for_status()
                address = response.json().get("address", {})
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("Reverse geocoding unavailable | error=%s", type(exc).__name__)

        primary_keys = (
            "neighbourhood",
            "suburb",
            "village",
            "hamlet",
            "city_district",
            "city",
            "town",
            "municipality",
            "county",
            "state_district",
        )
        context_keys = ("state", "country")

        def address_terms(keys):
            terms = []
            for key in keys:
                term = str(address.get(key, "")).strip()
                if term and term.casefold() not in {existing.casefold() for existing in terms}:
                    terms.append(term)
            return terms

        primary_terms = address_terms(primary_keys)
        context_terms = address_terms(context_keys)
        if not primary_terms:
            primary_terms = [fallback]
        terms = primary_terms + context_terms
        return {
            "display_name": ", ".join(terms[:4]),
            "country": str(address.get("country", "")),
            "query_terms": terms[:4],
            "validation_terms": terms[:6],
            "primary_terms": primary_terms[:6],
            "context_terms": context_terms,
            "center": {"lat": marker.y, "lon": marker.x},
        }

    @staticmethod
    def _search_query(area_terms: list[str], user_terms: list[str]) -> str:
        area_query = " OR ".join(f'"{term}"' for term in area_terms)
        user_query = " ".join(f'"{term}"' for term in user_terms)
        return f"({area_query}) {user_query}".strip()

    @staticmethod
    def _inclusive_end_date(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = GeoSearchService._as_utc(value)
        if normalized.time() == datetime.min.time():
            return normalized + timedelta(days=1) - timedelta(microseconds=1)
        return normalized

    @staticmethod
    def _google_date_query(
        start_date: datetime | None, end_date: datetime | None
    ) -> str:
        terms = []
        if start_date:
            start = GeoSearchService._as_utc(start_date) - timedelta(days=1)
            terms.append(f"after:{start.date().isoformat()}")
        if end_date:
            end = GeoSearchService._as_utc(end_date) + timedelta(days=1)
            terms.append(f"before:{end.date().isoformat()}")
        return " ".join(terms)

    @classmethod
    def _government_domains(cls, country: str) -> tuple[str, ...]:
        return cls.GOVERNMENT_DOMAINS.get(country.strip().casefold(), ())

    @classmethod
    async def _google_get(
        cls, client: httpx.AsyncClient, url: str
    ) -> httpx.Response:
        """Pace Google News RSS traffic shared by concurrent searches."""
        async with cls._google_request_lock:
            elapsed = time.monotonic() - cls._google_last_request_at
            delay = cls.GOOGLE_MIN_INTERVAL_SECONDS - elapsed
            if delay > 0:
                await asyncio.sleep(delay)
            cls._google_last_request_at = time.monotonic()
            return await client.get(url)

    @classmethod
    async def _fetch_in_place_batches(
        cls,
        fetch_batch,
        area_terms: list[str],
        user_terms: list[str],
        geometry: BaseGeometry,
        max_results: int,
        concurrency: int | None = None,
        *extra_args,
    ) -> dict[str, Any]:
        batches = [
            area_terms[index:index + cls.PLACE_BATCH_SIZE]
            for index in range(0, len(area_terms), cls.PLACE_BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(concurrency or cls.PROVIDER_CONCURRENCY)

        async def run_batch(batch):
            async with semaphore:
                return await fetch_batch(
                    batch, user_terms, geometry, min(max_results, 20), *extra_args
                )

        results = await asyncio.gather(*(run_batch(batch) for batch in batches))
        items = [item for result in results for item in result["items"]]
        items.sort(
            key=lambda item: cls._parse_datetime(item.get("published_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        items = items[:max_results]
        healthy = [result for result in results if result["status"] in {"success", "empty"}]
        if healthy:
            status = "success" if items else "empty"
            detail = None if len(healthy) == len(results) else "Some place batches failed"
        else:
            statuses = {result["status"] for result in results}
            status = "rate_limited" if statuses == {"rate_limited"} else "timeout" if statuses == {"timeout"} else "error"
            detail = "All place batches failed"
        return cls._provider_result(results[0]["name"], status, items, detail)

    @classmethod
    async def _fetch_google_news(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry,
        max_results: int, start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        return await cls._fetch_in_place_batches(
            cls._fetch_google_news_batch,
            area_terms,
            user_terms,
            geometry,
            max_results,
            None,
            start_date,
            end_date,
        )

    @classmethod
    async def _fetch_google_news_batch(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry,
        max_results: int, start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        name = "google_news"
        query = " ".join(filter(None, (
            cls._search_query(area_terms, user_terms),
            cls._google_date_query(start_date, end_date),
        )))
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await cls._google_get(client, url)
            if response.status_code == 429:
                return cls._provider_result(name, "rate_limited")
            response.raise_for_status()
            marker = geometry.representative_point()
            root = ET.fromstring(response.content)
            items = []
            for index, entry in enumerate(root.findall(".//item")[: max_results * 2]):
                link = (entry.findtext("link") or "").strip()
                title = (entry.findtext("title") or "News update").strip()
                source_node = entry.find("source")
                source = source_node.text.strip() if source_node is not None and source_node.text else "Google News"
                items.append(cls._raw_item(name, link or f"google-{index}", title, link, source, entry.findtext("description"), entry.findtext("pubDate"), marker))
            return cls._provider_result(name, "success" if items else "empty", items)
        except httpx.TimeoutException:
            return cls._provider_result(name, "timeout")
        except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
            logger.warning("Google News request failed | error=%s", type(exc).__name__)
            return cls._provider_result(name, "error", detail=type(exc).__name__)

    @classmethod
    async def _fetch_gdelt(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry,
        max_results: int, start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        # Large OR queries and many concurrent calls make the public GDELT
        # endpoint substantially slower. Use one bounded query per search.
        return await cls._fetch_gdelt_batch(
            area_terms[: cls.GDELT_QUERY_TERMS], user_terms, geometry,
            max_results, start_date, end_date,
        )

    @classmethod
    async def _fetch_gdelt_batch(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry,
        max_results: int, start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        name = "gdelt"
        params = cls._gdelt_params(
            cls._search_query(area_terms, user_terms), max_results, start_date, end_date
        )
        request_key = json.dumps(params, sort_keys=True, default=str)
        task = cls._gdelt_inflight.get(request_key)
        if task is None or task.done():
            task = asyncio.create_task(cls._request_gdelt(name, params, geometry))
            cls._gdelt_inflight[request_key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done() and cls._gdelt_inflight.get(request_key) is task:
                cls._gdelt_inflight.pop(request_key, None)

    @classmethod
    async def _fetch_government_news(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry,
        max_results: int, domains: tuple[str, ...], start_date: datetime | None,
        end_date: datetime | None,
    ) -> dict[str, Any]:
        name = "government"
        domain_query = " OR ".join(f"site:{domain}" for domain in domains)
        query = (
            f"{cls._search_query(area_terms[: cls.GDELT_QUERY_TERMS], user_terms)} "
            f"({domain_query}) {cls._google_date_query(start_date, end_date)}"
        ).strip()
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await cls._google_get(client, url)
            if response.status_code == 429:
                return cls._provider_result(name, "rate_limited")
            response.raise_for_status()
            marker = geometry.representative_point()
            root = ET.fromstring(response.content)
            items = []
            for index, entry in enumerate(root.findall(".//item")[: max_results * 3]):
                source_node = entry.find("source")
                source_url = (
                    source_node.attrib.get("url", "") if source_node is not None else ""
                )
                if not cls._is_allowed_domain(source_url, domains):
                    continue
                published_at = entry.findtext("pubDate")
                published = cls._parse_datetime(published_at)
                if start_date and (not published or published < cls._as_utc(start_date)):
                    continue
                if end_date and (not published or published > cls._as_utc(end_date)):
                    continue
                link = (entry.findtext("link") or "").strip()
                source = (
                    source_node.text.strip()
                    if source_node is not None and source_node.text
                    else urlparse(source_url).hostname or "Government"
                )
                items.append(cls._raw_item(
                    name, link or f"government-{index}",
                    (entry.findtext("title") or "Government update").strip(),
                    link, source, entry.findtext("description"), published_at, marker,
                ))
            return cls._provider_result(
                name, "success" if items else "empty", items[:max_results]
            )
        except httpx.TimeoutException:
            return cls._provider_result(name, "timeout", detail="Government search timed out")
        except (httpx.HTTPError, ET.ParseError, ValueError, TypeError) as exc:
            logger.warning("Government search failed | error=%s", type(exc).__name__)
            return cls._provider_result(name, "error", detail=type(exc).__name__)

    @staticmethod
    def _gdelt_params(
        query: str, max_results: int, start_date: datetime | None,
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
            params["startdatetime"] = GeoSearchService._as_gdelt_datetime(start_date)
        if end_date:
            params["enddatetime"] = GeoSearchService._as_gdelt_datetime(end_date)
        if not start_date and not end_date:
            params["timespan"] = "1month"
        return params

    @staticmethod
    def _as_gdelt_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    async def _wait_for_gdelt_rate_limit(cls) -> None:
        elapsed = time.monotonic() - cls._gdelt_last_request_at
        delay = cls.GDELT_MIN_INTERVAL_SECONDS - elapsed
        if delay > 0:
            await asyncio.sleep(delay)

    @classmethod
    async def _request_gdelt(
        cls, name: str, params: dict[str, Any], geometry: BaseGeometry,
        allowed_domains: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        last_status = "error"
        async with cls._gdelt_request_lock:
            async with httpx.AsyncClient(
                timeout=cls.GDELT_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                for endpoint_index, endpoint in enumerate(cls.GDELT_URLS):
                    await cls._wait_for_gdelt_rate_limit()
                    cls._gdelt_last_request_at = time.monotonic()
                    attempt = endpoint_index
                    request_started = time.perf_counter()
                    try:
                        response = await client.get(endpoint, params=params)
                        if response.status_code == 429:
                            return cls._provider_result(
                                name, "rate_limited",
                                detail="GDELT allows one request every five seconds",
                            )
                        response.raise_for_status()
                        articles = response.json().get("articles", [])
                        marker = geometry.representative_point()
                        items = []
                        for index, article in enumerate(articles):
                            url = str(article.get("url", ""))
                            if allowed_domains and not cls._is_allowed_domain(url, allowed_domains):
                                continue
                            items.append(cls._raw_item(
                                name, url or f"{name}-{index}",
                                article.get("title", "News article"), url,
                                article.get("domain", name.title()), None,
                                article.get("seendate"), marker,
                            ))
                        logger.info(
                            "%s request completed | endpoint=%s | results=%s | elapsed=%.3f",
                            name, "https" if endpoint_index == 0 else "http",
                            len(items), time.perf_counter() - request_started,
                        )
                        return cls._provider_result(
                            name, "success" if items else "empty", items
                        )
                    except httpx.TimeoutException:
                        last_status = "timeout"
                        logger.warning(
                            "%s request timed out | endpoint=%s",
                            name, "https" if endpoint_index == 0 else "http",
                        )
                    except (httpx.HTTPError, ValueError, TypeError) as exc:
                        last_status = "error"
                        logger.warning(
                            "%s request failed | endpoint=%s | error=%s",
                            name, "https" if endpoint_index == 0 else "http",
                            type(exc).__name__,
                        )
        return cls._provider_result(
            name, last_status,
            detail="GDELT connection failed on HTTPS and HTTP endpoints",
        )

    @staticmethod
    def _is_allowed_domain(url: str, allowed_domains: tuple[str, ...]) -> bool:
        hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in allowed_domains
        )

    @staticmethod
    def _raw_item(name: str, item_id: str, title: str, url: str, source: str, summary: str | None, published_at: str | None, marker: Point) -> dict[str, Any]:
        return {"id": str(item_id), "title": str(title), "url": str(url), "source": str(source), "summary": summary, "published_at": published_at, "provider": name, "lat": marker.y, "lon": marker.x}

    @staticmethod
    def _provider_result(name: str, status: str, items: list[dict[str, Any]] | None = None, detail: str | None = None) -> dict[str, Any]:
        return {"name": name, "status": status, "items": items or [], "detail": detail}

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        for parser in (
            lambda: parsedate_to_datetime(str(value)),
            lambda: datetime.strptime(str(value), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc),
            lambda: datetime.fromisoformat(str(value).replace("Z", "+00:00")),
        ):
            try:
                parsed = parser()
                return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        """Match a complete location/keyword phrase, not an arbitrary substring."""
        words = [re.escape(part) for part in term.casefold().split() if part]
        if not words:
            return False
        pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
        return re.search(pattern, text) is not None

    @classmethod
    def _rank_filter_and_deduplicate(
        cls,
        items: list[dict[str, Any]],
        geometry: BaseGeometry,
        primary_area_terms: list[str],
        discovered_area_terms: list[str],
        context_terms: list[str],
        query_is_geographically_constrained: bool,
        user_terms: list[str],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[NewsItem]:
        start = start_date.astimezone(timezone.utc) if start_date and start_date.tzinfo else start_date.replace(tzinfo=timezone.utc) if start_date else None
        end = end_date.astimezone(timezone.utc) if end_date and end_date.tzinfo else end_date.replace(tzinfo=timezone.utc) if end_date else None
        candidates: dict[str, NewsItem] = {}
        for item in items:
            if not item["url"]:
                continue
            if not geometry.covers(Point(item["lon"], item["lat"])):
                continue
            published = cls._parse_datetime(item["published_at"])
            if (start and (not published or published < start)) or (end and (not published or published > end)):
                continue
            text = " ".join(str(item.get(key) or "") for key in ("title", "summary", "source")).casefold()
            primary_matches = [
                term for term in primary_area_terms
                if cls._contains_term(text, term)
            ]
            discovered_matches = [
                term for term in discovered_area_terms
                if cls._contains_term(text, term)
            ]
            context_matches = [
                term for term in context_terms if cls._contains_term(text, term)
            ]
            has_explicit_location_match = bool(
                primary_matches or discovered_matches
            )
            if not has_explicit_location_match and not query_is_geographically_constrained:
                continue
            matched = list(dict.fromkeys(
                primary_matches + discovered_matches + context_matches
            ))
            user_matches = sum(
                cls._contains_term(text, term) for term in user_terms
            )
            relevance = min(100, 55 + len(matched) * 10 + user_matches * 5)
            normalized_title = " ".join(str(item["title"]).casefold().split())
            dedupe_value = normalized_title or item["url"] or item["id"]
            dedupe_key = hashlib.sha256(dedupe_value.encode("utf-8")).hexdigest()
            candidate = NewsItem(
                **{key: item[key] for key in ("id", "title", "url", "source", "provider", "lat", "lon")},
                summary=item.get("summary"),
                published_at=published,
                area_relevance=relevance,
                trust_score=95 if item["provider"] == "government" else 75 if item["provider"] == "gdelt" else 70,
                location_evidence=(
                    [f"{term} mentioned in result" for term in matched]
                    if matched
                    else [
                        "Provider query constrained to selected area and administrative context"
                    ]
                ),
            )
            existing = candidates.get(dedupe_key)
            if existing is None or (
                candidate.provider == "government" and existing.provider != "government"
            ):
                candidates[dedupe_key] = candidate
        return list(candidates.values())
