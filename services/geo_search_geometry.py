import json
from typing import Any

import httpx
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from database.database import SessionLocal
from models.model import Feature
from services.geo_search_utils import MAX_AREA_SQUARE_DEGREES, REQUEST_TIMEOUT, USER_AGENT
from utils.constants import (
    GEO_SEARCH_AREA_TOO_LARGE,
    GEO_SEARCH_FEATURE_BOUNDS_INVALID,
    GEO_SEARCH_FEATURE_EMPTY_GEOMETRY,
    GEO_SEARCH_FEATURE_EMPTY_SHAPE,
    GEO_SEARCH_FEATURE_INVALID_GEOMETRY,
    GEO_SEARCH_FEATURE_LOAD_FAILED,
    GEO_SEARCH_FEATURE_NOT_FOUND,
)
from utils.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from utils.logger import logger


async def feature_geometry(
    case_id: int, layer_id: int, feature_number: int
) -> BaseGeometry:
    logger.info(
        "Loading Geo Search feature | case_id=%s | layer_id=%s | feature_number=%s",
        case_id,
        layer_id,
        feature_number,
    )
    row = await run_in_threadpool(_feature_row, case_id, layer_id, feature_number)
    if row is None:
        raise NotFoundError(GEO_SEARCH_FEATURE_NOT_FOUND)
    if not row.geometry:
        raise UnprocessableEntityError(GEO_SEARCH_FEATURE_EMPTY_GEOMETRY)
    try:
        geometry = shape(json.loads(row.geometry))
    except (TypeError, ValueError) as exc:
        logger.error(
            "Stored feature geometry is invalid | feature_number=%s",
            feature_number,
        )
        raise UnprocessableEntityError(GEO_SEARCH_FEATURE_INVALID_GEOMETRY) from exc
    return await validate_geometry(geometry)


def _feature_row(case_id: int, layer_id: int, feature_number: int):
    try:
        with SessionLocal() as db:
            return db.execute(
                select(Feature.id, func.ST_AsGeoJSON(Feature.geom).label("geometry"))
                .where(
                    Feature.feature_number == feature_number,
                    Feature.layer_id == layer_id,
                    Feature.case_id == case_id,
                )
            ).one_or_none()
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to load Geo Search feature | case_id=%s | layer_id=%s | "
            "feature_number=%s | error=%s",
            case_id,
            layer_id,
            feature_number,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(GEO_SEARCH_FEATURE_LOAD_FAILED) from exc


async def validate_geometry(geometry: BaseGeometry) -> BaseGeometry:
    if geometry.is_empty:
        raise UnprocessableEntityError(GEO_SEARCH_FEATURE_EMPTY_SHAPE)
    if not geometry.is_valid:
        raise UnprocessableEntityError(
            f"{GEO_SEARCH_FEATURE_INVALID_GEOMETRY}: {explain_validity(geometry)}"
        )
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
        raise UnprocessableEntityError(GEO_SEARCH_FEATURE_BOUNDS_INVALID)
    if (max_lon - min_lon) * (max_lat - min_lat) > MAX_AREA_SQUARE_DEGREES:
        raise BadRequestError(GEO_SEARCH_AREA_TOO_LARGE)
    return geometry


async def area_context(geometry: BaseGeometry) -> dict[str, Any]:
    marker = geometry.representative_point()
    fallback = f"{marker.y:.4f},{marker.x:.4f}"
    address: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        ) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": marker.y,
                    "lon": marker.x,
                    "format": "jsonv2",
                    "addressdetails": 1,
                },
            )
            response.raise_for_status()
            address = response.json().get("address", {})
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Reverse geocoding unavailable | error=%s", type(exc).__name__)

    primary_terms = await _address_terms(
        address,
        (
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
        ),
    )
    context_terms = await _address_terms(address, ("state", "country"))
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


async def _address_terms(address: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    terms = []
    for key in keys:
        term = str(address.get(key, "")).strip()
        if term and term.casefold() not in {existing.casefold() for existing in terms}:
            terms.append(term)
    return terms
