import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field
from shapely.geometry import Point


USER_AGENT = "GeoIntelligence-GeoSearch/2.1 (news-search)"
REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
GDELT_TIMEOUT = httpx.Timeout(15.0, connect=3.0)
GDELT_URLS = (
    "https://api.gdeltproject.org/api/v2/doc/doc",
    "http://api.gdeltproject.org/api/v2/doc/doc",
)
GDELT_MIN_INTERVAL_SECONDS = 5.1
GOOGLE_MIN_INTERVAL_SECONDS = 0.75
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

gdelt_request_lock = asyncio.Lock()
gdelt_last_request_at = 0.0
gdelt_inflight: dict[str, asyncio.Task] = {}
google_request_lock = asyncio.Lock()
google_last_request_at = 0.0
place_cache: dict[str, tuple[float, list[str]]] = {}


class RawNewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    summary: str | None = None
    published_at: Any = None
    provider: str
    lat: float
    lon: float


class ProviderResult(BaseModel):
    name: str
    status: Literal["success", "empty", "timeout", "rate_limited", "error"]
    items: list[RawNewsItem] = Field(default_factory=list)
    detail: str | None = None


async def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def inclusive_end_date(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    normalized = await as_utc(value)
    if normalized.time() == datetime.min.time():
        return normalized + timedelta(days=1) - timedelta(microseconds=1)
    return normalized


async def google_date_query(
    start_date: datetime | None, end_date: datetime | None
) -> str:
    terms = []
    if start_date:
        start = await as_utc(start_date)
        terms.append(f"after:{(start - timedelta(days=1)).date().isoformat()}")
    if end_date:
        end = await as_utc(end_date)
        terms.append(f"before:{(end + timedelta(days=1)).date().isoformat()}")
    return " ".join(terms)


async def as_gdelt_datetime(value: datetime) -> str:
    return (await as_utc(value)).strftime("%Y%m%d%H%M%S")


async def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsers = (
        lambda: parsedate_to_datetime(str(value)),
        lambda: datetime.strptime(str(value), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        ),
        lambda: datetime.fromisoformat(str(value).replace("Z", "+00:00")),
    )
    for parser in parsers:
        try:
            parsed = parser()
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


async def search_query(area_terms: list[str], user_terms: list[str]) -> str:
    area_query = " OR ".join(f'"{term}"' for term in area_terms)
    user_query = " ".join(f'"{term}"' for term in user_terms)
    return f"({area_query}) {user_query}".strip()


async def government_domains(country: str) -> tuple[str, ...]:
    return GOVERNMENT_DOMAINS.get(country.strip().casefold(), ())


async def is_allowed_domain(url: str, allowed_domains: tuple[str, ...]) -> bool:
    hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in allowed_domains
    )


async def raw_item(
    name: str,
    item_id: str,
    title: str,
    url: str,
    source: str,
    summary: str | None,
    published_at: str | None,
    marker: Point,
) -> RawNewsItem:
    return RawNewsItem(
        id=str(item_id),
        title=str(title),
        url=str(url),
        source=str(source),
        summary=summary,
        published_at=published_at,
        provider=name,
        lat=marker.y,
        lon=marker.x,
    )


async def provider_result(
    name: str,
    status: str,
    items: list[RawNewsItem] | None = None,
    detail: str | None = None,
) -> ProviderResult:
    return ProviderResult(name=name, status=status, items=items or [], detail=detail)
