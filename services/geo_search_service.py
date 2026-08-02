import asyncio
import time
from datetime import datetime, timezone

from schemas.geo_search_schema import (
    GeoSearchRequest,
    GeoSearchResponse,
    GeoSearchSelection,
    SourceStatus,
)
from services.geo_search_gdelt import fetch_gdelt
from services.geo_search_geometry import area_context, feature_geometry
from services.geo_search_google import fetch_google_news, fetch_government_news
from services.geo_search_places import discover_places
from services.geo_search_ranking import rank_filter_and_deduplicate
from services.geo_search_utils import (
    MAX_DISCOVERED_PLACES,
    PROVIDER_CANDIDATE_LIMIT,
    government_domains,
    inclusive_end_date,
)
from utils.exceptions import GatewayTimeoutError, NotFoundError, ServiceUnavailableError
from utils.constants import (
    GEO_SEARCH_NO_RESULTS,
    GEO_SEARCH_PROVIDER_EMPTY,
    GEO_SEARCH_PROVIDER_TIMEOUT,
    GEO_SEARCH_PROVIDERS_UNAVAILABLE,
    GEO_SEARCH_STATUS_PARTIAL_SUCCESS,
    GEO_SEARCH_STATUS_SUCCESS,
    GEO_SEARCH_STATUS_UPSTREAM_UNAVAILABLE,
    GEO_SEARCH_TIMEOUT,
)
from utils.logger import logger


class GeoSearchService:
    """Build and execute a bounded, live, news-only geographic search."""

    @classmethod
    async def execute_news_search(
        cls, request: GeoSearchRequest
    ) -> GeoSearchResponse:
        started_at = time.perf_counter()
        geometry = await feature_geometry(
            request.case_id, request.layer_id, request.feature_number
        )
        area, place_result = await asyncio.gather(
            area_context(geometry),
            discover_places(geometry),
        )
        places, discovery_status = place_result
        places = places[:MAX_DISCOVERED_PLACES]
        effective_end = await inclusive_end_date(request.end_date)
        primary_terms = area["primary_terms"]
        context_terms = area["context_terms"]
        search_terms = list(dict.fromkeys(primary_terms + places))
        provider_terms = request.keywords + context_terms[:1]
        area.update({
            "searched_places": search_terms,
            "searched_places_count": len(search_terms),
            "place_discovery_status": discovery_status,
        })

        provider_results = await cls._provider_results(
            search_terms,
            provider_terms,
            geometry,
            area.get("country", ""),
            request.start_date,
            effective_end,
        )
        items = [item for result in provider_results for item in result.items]
        items = await rank_filter_and_deduplicate(
            items=items,
            geometry=geometry,
            primary_area_terms=primary_terms,
            discovered_area_terms=places,
            context_terms=context_terms,
            user_terms=request.keywords,
            start_date=request.start_date,
            end_date=effective_end,
        )
        items.sort(
            key=lambda item: item.published_at
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        items = items[:request.max_results]
        await cls._raise_when_no_items(items, provider_results)
        sources = {
            result.name: SourceStatus(
                status=result.status,
                results=len(result.items),
                accepted_results=sum(item.provider == result.name for item in items),
                detail=result.detail,
            )
            for result in provider_results
        }
        aggregate_status = await cls._aggregate_status(provider_results)
        logger.info(
            "Geo news search completed | status=%s | results=%s | elapsed=%.3f",
            aggregate_status,
            len(items),
            time.perf_counter() - started_at,
        )
        return GeoSearchResponse(
            status=aggregate_status,
            total_results=len(items),
            execution_time_seconds=round(time.perf_counter() - started_at, 3),
            selection=GeoSearchSelection(
                case_id=request.case_id,
                layer_id=request.layer_id,
                feature_number=request.feature_number,
            ),
            area=area,
            sources=sources,
            items=items,
        )

    @classmethod
    async def _provider_results(
        cls,
        search_terms,
        provider_terms,
        geometry,
        country,
        start_date,
        end_date,
    ):
        domains = await government_domains(country)
        calls = [
            fetch_google_news(
                search_terms, provider_terms, geometry,
                PROVIDER_CANDIDATE_LIMIT, start_date, end_date,
            ),
            fetch_gdelt(
                search_terms, provider_terms, geometry,
                PROVIDER_CANDIDATE_LIMIT, start_date, end_date,
            ),
        ]
        if domains:
            calls.append(fetch_government_news(
                search_terms,
                provider_terms,
                geometry,
                PROVIDER_CANDIDATE_LIMIT,
                domains,
                start_date,
                end_date,
            ))
        return await asyncio.gather(*calls)

    @classmethod
    async def _raise_when_no_items(cls, items, provider_results) -> None:
        if items:
            return
        statuses = {result.status for result in provider_results}
        healthy_results = [
            result for result in provider_results
            if result.status in {GEO_SEARCH_STATUS_SUCCESS, GEO_SEARCH_PROVIDER_EMPTY}
        ]
        logger.warning(
            "Geo news search produced no usable results | providers=%s",
            {
                result.name: {
                    "status": result.status,
                    "results": len(result.items),
                    "detail": result.detail,
                }
                for result in provider_results
            },
        )
        if not healthy_results and GEO_SEARCH_PROVIDER_TIMEOUT in statuses:
            raise GatewayTimeoutError(GEO_SEARCH_TIMEOUT)
        if healthy_results:
            raise NotFoundError(GEO_SEARCH_NO_RESULTS)
        raise ServiceUnavailableError(GEO_SEARCH_PROVIDERS_UNAVAILABLE)

    @classmethod
    async def _aggregate_status(cls, provider_results) -> str:
        healthy = sum(
            result.status in {GEO_SEARCH_STATUS_SUCCESS, GEO_SEARCH_PROVIDER_EMPTY}
            for result in provider_results
        )
        if healthy == len(provider_results):
            return GEO_SEARCH_STATUS_SUCCESS
        if healthy:
            return GEO_SEARCH_STATUS_PARTIAL_SUCCESS
        return GEO_SEARCH_STATUS_UPSTREAM_UNAVAILABLE
