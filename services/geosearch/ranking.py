import hashlib
import re
from datetime import datetime, timezone

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from schemas.geo_search_schema import NewsItem
from services.geosearch.utils import RawNewsItem, parse_datetime


async def rank_filter_and_deduplicate(
    items: list[RawNewsItem],
    geometry: BaseGeometry,
    primary_area_terms: list[str],
    discovered_area_terms: list[str],
    context_terms: list[str],
    user_terms: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[NewsItem]:
    start = await _normalized_boundary(start_date)
    end = await _normalized_boundary(end_date)
    candidates: dict[str, NewsItem] = {}
    for item in items:
        candidate = await _candidate(
            item, geometry, primary_area_terms, discovered_area_terms,
            context_terms, user_terms, start, end,
        )
        if candidate is None:
            continue
        dedupe_key = await _dedupe_key(candidate)
        existing = candidates.get(dedupe_key)
        if existing is None or (
            candidate.provider == "government" and existing.provider != "government"
        ):
            candidates[dedupe_key] = candidate
    return list(candidates.values())


async def contains_term(text: str, term: str) -> bool:
    words = [re.escape(part) for part in term.casefold().split() if part]
    if not words:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"
    return re.search(pattern, text) is not None


async def geographic_evidence_strength(
    primary_matches: list[str],
    discovered_matches: list[str],
    context_matches: list[str],
    primary_area_terms: list[str],
) -> int:
    local_matches = list(dict.fromkeys(primary_matches + discovered_matches))
    if local_matches and context_matches:
        return 3
    if len(local_matches) >= 2:
        return 3
    if context_matches:
        return 2
    administrative_terms = {term.casefold() for term in primary_area_terms[1:]}
    if any(term.casefold() in administrative_terms for term in local_matches):
        return 2
    if any(len(term.split()) > 1 for term in local_matches):
        return 2
    return 1 if local_matches else 0


async def _candidate(
    item: RawNewsItem,
    geometry: BaseGeometry,
    primary_area_terms: list[str],
    discovered_area_terms: list[str],
    context_terms: list[str],
    user_terms: list[str],
    start: datetime | None,
    end: datetime | None,
) -> NewsItem | None:
    if not item.url or not geometry.covers(Point(item.lon, item.lat)):
        return None
    published = await parse_datetime(item.published_at)
    if (start and (not published or published < start)) or (
        end and (not published or published > end)
    ):
        return None
    text = " ".join((item.title, item.summary or "", item.source)).casefold()
    primary_matches = await _matches(text, primary_area_terms)
    discovered_matches = await _matches(text, discovered_area_terms)
    context_matches = await _matches(text, context_terms)
    user_matches = sum([await contains_term(text, term) for term in user_terms])
    if user_terms and not user_matches:
        return None
    evidence = await geographic_evidence_strength(
        primary_matches, discovered_matches, context_matches, primary_area_terms
    )
    if evidence < 2:
        return None
    matched = list(dict.fromkeys(primary_matches + discovered_matches + context_matches))
    relevance = min(100, 45 + evidence * 10 + len(matched) * 5 + user_matches * 5)
    return NewsItem(
        id=item.id,
        title=item.title,
        url=item.url,
        source=item.source,
        provider=item.provider,
        lat=item.lat,
        lon=item.lon,
        summary=item.summary,
        published_at=published,
        area_relevance=relevance,
        trust_score=await _trust_score(item.provider),
        location_evidence=[f"{term} mentioned in result" for term in matched],
    )


async def _matches(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if await contains_term(text, term)]


async def _normalized_boundary(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)


async def _dedupe_key(item: NewsItem) -> str:
    normalized_title = " ".join(item.title.casefold().split())
    dedupe_value = normalized_title or item.url or item.id
    return hashlib.sha256(dedupe_value.encode("utf-8")).hexdigest()


async def _trust_score(provider: str) -> int:
    if provider == "government":
        return 95
    if provider == "gdelt":
        return 75
    return 70
