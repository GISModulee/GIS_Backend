import asyncio
import hashlib
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import h3
import httpx
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

from schemas.geo_search_schema import (
    GeoSearchRequest,
    GeoSearchResponse,
    GeometryInput,
    NewsItem,
    SourceStatus,
)
from utils.exceptions import BadRequestError
from utils.logger import logger


class GeoSearchService:
    """Build and execute a bounded, live, news-only geographic search."""

    USER_AGENT = "GeoIntelligence-GeoSearch/2.1 (news-search)"
    REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=4.0)
    MAX_AREA_SQUARE_DEGREES = 100.0

    @classmethod
    async def execute_news_search(
        cls, request: GeoSearchRequest
    ) -> GeoSearchResponse:
        started_at = time.perf_counter()
        geometry = cls._request_geometry(request)
        h3_cells = cls._h3_cells(geometry, request.h3_resolution)
        area = await cls._area_context(geometry)
        query_terms = area["query_terms"]

        provider_results = await asyncio.gather(
            cls._fetch_google_news(query_terms, request.keywords, geometry, request.max_results),
            cls._fetch_gdelt(query_terms, request.keywords, geometry, request.max_results),
        )

        items = [item for result in provider_results for item in result["items"]]
        items = cls._rank_filter_and_deduplicate(
            items=items,
            geometry=geometry,
            area_terms=area["validation_terms"],
            user_terms=request.keywords,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        items.sort(
            key=lambda item: (
                item.area_relevance,
                item.published_at or datetime.min.replace(tzinfo=timezone.utc),
                item.trust_score,
            ),
            reverse=True,
        )
        items = items[: request.max_results]

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
    def _request_geometry(cls, request: GeoSearchRequest) -> BaseGeometry:
        if request.single_shape:
            geometry = cls._parse_geometry(request.single_shape)
        else:
            operation = request.vector_op
            left = cls._parse_geometry(operation.shape_a)
            right = cls._parse_geometry(operation.shape_b)
            geometry = {
                "union": left.union,
                "intersection": left.intersection,
                "difference": left.difference,
            }[operation.operation](right)

        if geometry.is_empty:
            raise BadRequestError("Geometry operation produced an empty area.")
        if not geometry.is_valid:
            raise BadRequestError(f"Invalid geometry: {explain_validity(geometry)}")
        min_lon, min_lat, max_lon, max_lat = geometry.bounds
        if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
            raise BadRequestError("Geometry coordinates are outside valid longitude/latitude bounds.")
        if (max_lon - min_lon) * (max_lat - min_lat) > cls.MAX_AREA_SQUARE_DEGREES:
            raise BadRequestError("Search area is too large; submit a smaller geometry.")
        return geometry

    @staticmethod
    def _coordinate_pair(value: Any, field_name: str) -> tuple[float, float]:
        if not isinstance(value, list) or len(value) != 2:
            raise BadRequestError(f"{field_name} must be [longitude, latitude].")
        try:
            lon, lat = float(value[0]), float(value[1])
        except (TypeError, ValueError) as exc:
            raise BadRequestError(f"{field_name} must contain numeric coordinates.") from exc
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise BadRequestError(f"{field_name} is outside valid coordinate bounds.")
        return lon, lat

    @classmethod
    def _parse_geometry(cls, value: GeometryInput) -> BaseGeometry:
        coordinates = value.coordinates
        try:
            if value.type in {"Point", "Circle"}:
                lon, lat = cls._coordinate_pair(coordinates, "coordinates")
                radius = value.radius if value.type == "Circle" else 1_000.0
                return Point(lon, lat).buffer(radius / 111_320.0)
            if value.type == "LineString":
                if not isinstance(coordinates, list) or len(coordinates) < 2:
                    raise BadRequestError("LineString requires at least two coordinate pairs.")
                points = [cls._coordinate_pair(point, "LineString coordinate") for point in coordinates]
                return LineString(points).buffer((value.radius or 500.0) / 111_320.0)
            if value.type == "Rectangle":
                if not isinstance(coordinates, list) or len(coordinates) != 4:
                    raise BadRequestError("Rectangle coordinates must be [min_lon, min_lat, max_lon, max_lat].")
                min_lon, min_lat, max_lon, max_lat = map(float, coordinates)
                if min_lon >= max_lon or min_lat >= max_lat:
                    raise BadRequestError("Rectangle minimum coordinates must be below maximum coordinates.")
                return box(min_lon, min_lat, max_lon, max_lat)
            if value.type == "Polygon":
                rings = coordinates
                if rings and isinstance(rings[0], list) and rings[0] and isinstance(rings[0][0], (int, float)):
                    rings = [rings]
                if not isinstance(rings, list) or not rings or len(rings[0]) < 4:
                    raise BadRequestError("Polygon requires a closed ring with at least four coordinate pairs.")
                parsed_rings = [
                    [cls._coordinate_pair(point, "Polygon coordinate") for point in ring]
                    for ring in rings
                ]
                if any(ring[0] != ring[-1] for ring in parsed_rings):
                    raise BadRequestError("Every Polygon ring must be closed.")
                return Polygon(parsed_rings[0], parsed_rings[1:])
        except BadRequestError:
            raise
        except (TypeError, ValueError, IndexError) as exc:
            raise BadRequestError(f"Invalid {value.type} coordinates.") from exc
        raise BadRequestError(f"Unsupported geometry type: {value.type}")

    @staticmethod
    def _h3_cells(geometry: BaseGeometry, resolution: int) -> list[str]:
        try:
            return sorted(h3.geo_to_cells(mapping(geometry), resolution))
        except Exception as exc:
            logger.warning("H3 coverage failed | error=%s", exc)
            return []

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

        preferred_keys = ("neighbourhood", "suburb", "city_district", "city", "town", "county", "state", "country")
        terms = []
        for key in preferred_keys:
            term = str(address.get(key, "")).strip()
            if term and term.casefold() not in {existing.casefold() for existing in terms}:
                terms.append(term)
        if not terms:
            terms = [fallback]
        return {
            "display_name": ", ".join(terms[:4]),
            "country": str(address.get("country", "")),
            "query_terms": terms[:4],
            "validation_terms": terms[:6],
            "center": {"lat": marker.y, "lon": marker.x},
        }

    @staticmethod
    def _search_query(area_terms: list[str], user_terms: list[str]) -> str:
        area_query = " OR ".join(f'"{term}"' for term in area_terms[:3])
        user_query = " ".join(f'"{term}"' for term in user_terms)
        return f"({area_query}) {user_query}".strip()

    @classmethod
    async def _fetch_google_news(
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry, max_results: int
    ) -> dict[str, Any]:
        name = "google_news"
        query = cls._search_query(area_terms, user_terms)
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
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
        cls, area_terms: list[str], user_terms: list[str], geometry: BaseGeometry, max_results: int
    ) -> dict[str, Any]:
        name = "gdelt"
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                headers={"User-Agent": cls.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc",
                    params={"query": cls._search_query(area_terms, user_terms), "mode": "artlist", "maxrecords": min(max_results * 2, 250), "format": "json", "sort": "datedesc", "timespan": "1month"},
                )
            if response.status_code == 429:
                return cls._provider_result(name, "rate_limited")
            response.raise_for_status()
            marker = geometry.representative_point()
            items = [
                cls._raw_item(name, article.get("url", f"gdelt-{index}"), article.get("title", "News article"), article.get("url", ""), article.get("domain", "GDELT"), None, article.get("seendate"), marker)
                for index, article in enumerate(response.json().get("articles", []))
            ]
            return cls._provider_result(name, "success" if items else "empty", items)
        except httpx.TimeoutException:
            return cls._provider_result(name, "timeout")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("GDELT request failed | error=%s", type(exc).__name__)
            return cls._provider_result(name, "error", detail=type(exc).__name__)

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

    @classmethod
    def _rank_filter_and_deduplicate(
        cls,
        items: list[dict[str, Any]],
        geometry: BaseGeometry,
        area_terms: list[str],
        user_terms: list[str],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[NewsItem]:
        start = start_date.astimezone(timezone.utc) if start_date and start_date.tzinfo else start_date.replace(tzinfo=timezone.utc) if start_date else None
        end = end_date.astimezone(timezone.utc) if end_date and end_date.tzinfo else end_date.replace(tzinfo=timezone.utc) if end_date else None
        seen = set()
        accepted = []
        for item in items:
            dedupe_key = hashlib.sha256((item["url"] or item["id"]).encode("utf-8")).hexdigest()
            if dedupe_key in seen or not item["url"]:
                continue
            seen.add(dedupe_key)
            if not geometry.covers(Point(item["lon"], item["lat"])):
                continue
            published = cls._parse_datetime(item["published_at"])
            if (start and (not published or published < start)) or (end and (not published or published > end)):
                continue
            text = " ".join(str(item.get(key) or "") for key in ("title", "summary", "source")).casefold()
            matched = [term for term in area_terms if term.casefold() in text]
            user_matches = sum(term.casefold() in text for term in user_terms)
            relevance = min(100, (55 if matched else 25) + len(matched) * 10 + user_matches * 5)
            accepted.append(NewsItem(
                **{key: item[key] for key in ("id", "title", "url", "source", "provider", "lat", "lon")},
                summary=item.get("summary"),
                published_at=published,
                area_relevance=relevance,
                trust_score=75 if item["provider"] == "gdelt" else 70,
                location_evidence=[f"{term} mentioned in result" for term in matched] or ["Selected using shape-derived area query"],
            ))
        return accepted
