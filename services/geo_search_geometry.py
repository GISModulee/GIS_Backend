import json
from typing import Any

import httpx
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from models.model import Feature
from services.geo_search_utils import MAX_AREA_SQUARE_DEGREES, REQUEST_TIMEOUT, USER_AGENT
from utils.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from utils.logger import logger


async def feature_geometry(feature_id: int) -> BaseGeometry:
    logger.info("Loading Geo Search feature | feature_id=%s", feature_id)
    try:
        with SessionLocal() as db:
            row = db.execute(
                select(Feature.id, func.ST_AsGeoJSON(Feature.geom).label("geometry"))
                .where(Feature.id == feature_id)
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
        logger.error("Stored feature geometry is invalid | feature_id=%s", feature_id)
        raise UnprocessableEntityError("Selected feature has invalid geometry") from exc
    return await validate_geometry(geometry)


async def validate_geometry(geometry: BaseGeometry) -> BaseGeometry:
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
    if (max_lon - min_lon) * (max_lat - min_lat) > MAX_AREA_SQUARE_DEGREES:
        raise BadRequestError("Search area is too large; submit a smaller geometry.")
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
