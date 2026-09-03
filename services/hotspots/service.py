import json
import math

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database.mapserver_database import get_mapserver_db
from models.model import Feature, Layer
from schemas.feature_schema import FeatureCreate
from schemas.hotspot_schema import HotspotItem, HotspotRiskZone, HotspotSaveRequest, HotspotSearchRequest
from services.feature.feature_service import create_feature
from services.hotspots.categories import selected_categories
from services.hotspots.models import PlanetOsmPoint, PlanetOsmPolygon
from services.layer.layer_service import create_layer
from utils.constants import FEATURE_NOT_FOUND, LAYER_NOT_FOUND
from utils.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from utils.logger import logger


async def search_hotspots(request: HotspotSearchRequest, db: Session) -> dict:
    area_wkt = await _selected_feature_wkt(request, db)
    categories = selected_categories(request.category_groups)
    rows = await run_in_threadpool(
        _query_mapserver_points,
        area_wkt,
        categories,
        request.limit,
        request.range_meters,
    )
    category_counts = await run_in_threadpool(
        _query_category_counts,
        area_wkt,
        categories,
        request.range_meters,
    )
    items = [_row_to_hotspot(row, categories) for row in rows]
    risk_zones = _risk_zones(items)
    return {
        "status": "success",
        "case_id": request.case_id,
        "layer_id": request.layer_id,
        "feature_number": request.feature_number,
        "count": len(items),
        "category_counts": category_counts,
        "items": items,
        "risk_zones": risk_zones,
    }


async def save_hotspots(request: HotspotSaveRequest, db: Session, current_user: dict) -> dict:
    await _selected_feature_wkt(
        HotspotSearchRequest(
            case_id=request.case_id,
            layer_id=request.source_layer_id,
            feature_number=request.source_feature_number,
        ),
        db,
    )
    layer_id = await _target_layer_id(request, db)
    existing = await _existing_osm_ids(request.case_id, layer_id, db)
    saved_ids, saved_numbers, skipped = [], [], 0

    for hotspot in request.hotspots:
        if hotspot.osm_id in existing:
            skipped += 1
            continue

        result = await create_feature(
            FeatureCreate(
                case_id=request.case_id,
                layer_id=layer_id,
                name=hotspot.name or f"Hotspot {hotspot.osm_id}",
                geometry={"type": "Point", "coordinates": hotspot.coordinates},
                geometry_type="Point",
                properties={
                    "source": "mapserver",
                    "osm_id": hotspot.osm_id,
                    "category_group": hotspot.category,
                    "category_value": hotspot.type,
                    "priority": hotspot.priority,
                    "source_layer_id": request.source_layer_id,
                    "source_feature_number": request.source_feature_number,
                },
            ),
            db,
            current_user["user_id"],
        )
        existing.add(hotspot.osm_id)
        saved_ids.append(result["feature_id"])
        saved_numbers.append(result["feature_number"])

    return {
        "success": True,
        "case_id": request.case_id,
        "layer_id": layer_id,
        "saved_count": len(saved_ids),
        "skipped_count": skipped,
        "feature_ids": saved_ids,
        "feature_numbers": saved_numbers,
    }


async def _selected_feature_wkt(request: HotspotSearchRequest, db: Session) -> str:
    layer = db.get(Layer, request.layer_id)
    if layer is None or layer.case_id != request.case_id:
        raise NotFoundError(LAYER_NOT_FOUND)

    wkt = db.scalar(
        select(func.ST_AsEWKT(Feature.geom)).where(
            Feature.case_id == request.case_id,
            Feature.layer_id == request.layer_id,
            Feature.feature_number == request.feature_number,
        )
    )
    if not wkt:
        raise NotFoundError(FEATURE_NOT_FOUND)
    return wkt


def _query_mapserver_points(area_wkt: str, categories: dict, limit: int, range_meters: int | None) -> list:
    map_db = get_mapserver_db()
    if map_db is None:
        raise ServiceUnavailableError("MapServer database is not configured")

    try:
        priority_cases = []
        priority_rank = {"high": 1, "medium": 2, "low": 3}

        area = func.ST_Transform(func.ST_GeomFromEWKT(area_wkt), 3857)
        point_rows = list(map_db.execute(
            _hotspot_statement(PlanetOsmPoint, PlanetOsmPoint.way, area, categories, priority_rank, range_meters, limit)
        ))
        polygon_marker = func.ST_PointOnSurface(PlanetOsmPolygon.way)
        polygon_rows = list(map_db.execute(
            _hotspot_statement(PlanetOsmPolygon, polygon_marker, area, categories, priority_rank, range_meters, limit)
        ))
        return _merge_hotspot_rows(point_rows, polygon_rows, categories, priority_rank, limit)
    except SQLAlchemyError as exc:
        logger.error("Hotspot MapServer query failed | error=%s", exc, exc_info=True)
        raise ServiceUnavailableError("Failed to search hotspots") from exc
    finally:
        map_db.close()


def _hotspot_statement(model, marker, area, categories: dict, priority_rank: dict, range_meters: int | None, limit: int):
    filters = []
    priority_cases = []
    for config in categories.values():
        for rule in config["rules"]:
            column = getattr(model, rule["column"], None)
            if column is None:
                raise BadRequestError(f"Unsupported hotspot category column: {rule['column']}")
            filters.append(column.in_(list(rule["values"])))
            priority_cases.extend(
                (column == value, priority_rank[priority])
                for value, priority in rule["values"].items()
            )

    center = func.ST_PointOnSurface(area)
    distance = func.ST_Distance(marker, center)
    priority_order = case(*priority_cases, else_=4)
    spatial_filter = func.ST_Within(marker, area)
    if model is PlanetOsmPolygon and range_meters is None:
        spatial_filter = func.ST_Intersects(model.way, area)
    if range_meters is not None:
        spatial_filter = func.ST_DWithin(marker, center, range_meters)

    return (
        select(
            model.osm_id,
            model.name,
            model.aeroway,
            model.amenity,
            model.railway,
            model.shop,
            model.tourism,
            model.place,
            model.building,
            model.leisure,
            distance.label("distance_m"),
            func.ST_AsGeoJSON(func.ST_Transform(marker, 4326)).label("geometry"),
        )
        .where(or_(*filters), spatial_filter)
        .order_by(priority_order, distance, model.name.is_(None), model.name, model.osm_id)
        .limit(limit)
    )


def _query_category_counts(area_wkt: str, categories: dict, range_meters: int | None) -> dict[str, int]:
    map_db = get_mapserver_db()
    if map_db is None:
        raise ServiceUnavailableError("MapServer database is not configured")

    try:
        area = func.ST_Transform(func.ST_GeomFromEWKT(area_wkt), 3857)
        counts = {}
        for group, config in categories.items():
            point_count = map_db.scalar(
                _hotspot_count_statement(PlanetOsmPoint, PlanetOsmPoint.way, area, config, range_meters)
            ) or 0
            polygon_marker = func.ST_PointOnSurface(PlanetOsmPolygon.way)
            polygon_count = map_db.scalar(
                _hotspot_count_statement(PlanetOsmPolygon, polygon_marker, area, config, range_meters)
            ) or 0
            counts[group] = int(point_count) + int(polygon_count)
        return counts
    except SQLAlchemyError as exc:
        logger.error("Hotspot category count query failed | error=%s", exc, exc_info=True)
        raise ServiceUnavailableError("Failed to search hotspots") from exc
    finally:
        map_db.close()


def _hotspot_count_statement(model, marker, area, config: dict, range_meters: int | None):
    filters = []
    for rule in config["rules"]:
        column = getattr(model, rule["column"], None)
        if column is None:
            raise BadRequestError(f"Unsupported hotspot category column: {rule['column']}")
        filters.append(column.in_(list(rule["values"])))

    center = func.ST_PointOnSurface(area)
    spatial_filter = func.ST_Within(marker, area)
    if model is PlanetOsmPolygon and range_meters is None:
        spatial_filter = func.ST_Intersects(model.way, area)
    if range_meters is not None:
        spatial_filter = func.ST_DWithin(marker, center, range_meters)

    return select(func.count()).where(or_(*filters), spatial_filter)


def _merge_hotspot_rows(point_rows: list, polygon_rows: list, categories: dict, priority_rank: dict, limit: int) -> list:
    rows_by_osm_id = {}
    for row in point_rows + polygon_rows:
        existing = rows_by_osm_id.get(row.osm_id)
        if existing is None or _row_sort_key(row, categories, priority_rank) < _row_sort_key(existing, categories, priority_rank):
            rows_by_osm_id[row.osm_id] = row
    return sorted(rows_by_osm_id.values(), key=lambda row: _row_sort_key(row, categories, priority_rank))[:limit]


def _row_sort_key(row, categories: dict, priority_rank: dict) -> tuple:
    priority = _row_priority_rank(row, categories, priority_rank)
    distance = float(row.distance_m) if row.distance_m is not None else float("inf")
    name = row.name or ""
    return (priority, distance, name.casefold(), row.osm_id)


def _row_priority_rank(row, categories: dict, priority_rank: dict) -> int:
    values = {
        "amenity": row.amenity,
        "aeroway": row.aeroway,
        "railway": row.railway,
        "shop": row.shop,
        "tourism": row.tourism,
        "place": row.place,
        "building": row.building,
        "leisure": row.leisure,
    }
    for config in categories.values():
        for rule in config["rules"]:
            value = values.get(rule["column"])
            priority = rule["values"].get(value)
            if priority is not None:
                return priority_rank[priority]
    return 4


def _row_to_hotspot(row, categories: dict) -> HotspotItem:
    values = {
        "amenity": row.amenity,
        "aeroway": row.aeroway,
        "railway": row.railway,
        "shop": row.shop,
        "tourism": row.tourism,
        "place": row.place,
        "building": row.building,
        "leisure": row.leisure,
    }
    for group, config in categories.items():
        for rule in config["rules"]:
            value = values.get(rule["column"])
            if value in rule["values"]:
                geometry = json.loads(row.geometry)
                return HotspotItem(
                    osm_id=row.osm_id,
                    name=row.name,
                    type=value,
                    category=group,
                    priority=rule["values"][value],
                    distance_m=round(float(row.distance_m), 2) if row.distance_m is not None else None,
                    coordinates=geometry["coordinates"],
                )
    raise BadRequestError("Hotspot result did not match a configured category")


def _risk_zones(items: list[HotspotItem]) -> list[HotspotRiskZone]:
    important = [item for item in items if item.priority in {"high", "medium"}]
    zones = []
    used: set[int] = set()

    for index, item in enumerate(important):
        if index in used:
            continue

        cluster = [
            other
            for other in important
            if _distance_m(item.coordinates, other.coordinates) <= 300
        ]
        if len(cluster) < 3:
            continue

        cluster_indexes = {
            other_index
            for other_index, other in enumerate(important)
            if _distance_m(item.coordinates, other.coordinates) <= 300
        }
        used.update(cluster_indexes)

        high_count = sum(other.priority == "high" for other in cluster)
        medium_count = sum(other.priority == "medium" for other in cluster)
        priority = "high" if len(cluster) >= 5 or high_count >= 3 else "medium"
        center_lng = sum(other.coordinates[0] for other in cluster) / len(cluster)
        center_lat = sum(other.coordinates[1] for other in cluster) / len(cluster)

        zones.append(
            HotspotRiskZone(
                zone_id=f"zone_{len(zones) + 1}",
                priority=priority,
                center=[center_lng, center_lat],
                radius_m=300,
                hotspot_count=len(cluster),
                high_count=high_count,
                medium_count=medium_count,
            )
        )

    return zones


def _distance_m(left: list[float], right: list[float]) -> float:
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    haversine = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(haversine))


async def _target_layer_id(request: HotspotSaveRequest, db: Session) -> int:
    if request.target_layer_id is not None:
        layer = db.get(Layer, request.target_layer_id)
        if layer is None or layer.case_id != request.case_id:
            raise NotFoundError(LAYER_NOT_FOUND)
        return request.target_layer_id

    layer_name = request.layer_name or await _default_layer_name(
        request.case_id,
        request.source_layer_id,
        request.source_feature_number,
        db,
    )
    existing = db.scalar(
        select(Layer.id).where(
            Layer.case_id == request.case_id,
            Layer.name == layer_name,
            Layer.layer_type == "hotspot",
        )
    )
    if existing is not None:
        return existing

    created = await create_layer(
        {"case_id": request.case_id, "name": layer_name, "layer_type": "hotspot", "visible": True},
        db,
    )
    return created["layer_id"]


async def _existing_osm_ids(case_id: int, layer_id: int, db: Session) -> set[int]:
    rows = db.scalars(
        select(Feature.properties).where(
            Feature.case_id == case_id,
            Feature.layer_id == layer_id,
        )
    )
    return {
        int(properties["osm_id"])
        for properties in rows
        if isinstance(properties, dict) and properties.get("source") == "mapserver" and properties.get("osm_id")
    }


async def _default_layer_name(case_id: int, layer_id: int, feature_number: int, db: Session) -> str:
    name = db.scalar(
        select(Feature.name).where(
            Feature.case_id == case_id,
            Feature.layer_id == layer_id,
            Feature.feature_number == feature_number,
        )
    )
    display_name = (name or f"Feature {feature_number}").strip()
    return f"HS - {display_name}"[:100]
