import json
import math

import httpx
from pydantic import ValidationError
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import SQLAlchemyError

from models.model import (
    EmailDump,
    EmailRecord,
    EmailTarget,
    EmailTargetEmail,
    Feature,
    Layer,
)
from schemas.email_dump_schema import (
    EmailDumpOriginIpImportResponse,
    EmailDumpOriginIpQuery,
    EmailDumpOriginIpResponse,
    EmailDumpRef,
    EmailOriginIpRecord,
    EmailTargetRef,
    OriginIpCount,
)
from services.feature.feature_websocket_manager import feature_connection_manager
from services.feature.feature_service import create_features_batch
from services.layer.layer_websocket_manager import layer_connection_manager
from services.layer.layer_service import create_layer, get_layer
from utils.config import settings
from utils.constants import (
    EMAIL_DUMP_FEATURE_NAME_TEMPLATE,
    EMAIL_DUMP_IMPORT_FAILED,
    EMAIL_DUMP_INVALID_RESPONSE,
    EMAIL_DUMP_LAYER_NAME_TEMPLATE,
    EMAIL_DUMP_LAYER_TYPE,
    EMAIL_DUMP_MODULE_SLUG,
    EMAIL_DUMP_NOT_CONFIGURED,
    EMAIL_DUMP_NOT_FOUND,
    EMAIL_DUMP_ORIGIN_IPS_PATH,
    EMAIL_DUMP_RATE_LIMITED,
    EMAIL_DUMP_TIMEOUT,
    EMAIL_DUMP_UNAUTHORIZED,
    EMAIL_DUMP_UNAVAILABLE,
    STATUS_FORBIDDEN,
    STATUS_NOT_FOUND,
    STATUS_TOO_MANY_REQUESTS,
    STATUS_UNAUTHORIZED,
)
from utils.exceptions import (
    AppException,
    GatewayTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from utils.logger import logger


def build_origin_ips_url(case_id: int) -> str:
    base_url = (settings.EMAIL_DUMP_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("Email Dump base URL is not configured")
        raise ServiceUnavailableError(EMAIL_DUMP_NOT_CONFIGURED)
    return f"{base_url}{EMAIL_DUMP_ORIGIN_IPS_PATH}/{case_id}"


def layer_name_for_email(email_id: int) -> str:
    return EMAIL_DUMP_LAYER_NAME_TEMPLATE.format(email_id=email_id)


def _provider_error(status_code: int) -> AppException:
    if status_code in (STATUS_UNAUTHORIZED, STATUS_FORBIDDEN):
        return UnauthorizedError(EMAIL_DUMP_UNAUTHORIZED)
    if status_code == STATUS_NOT_FOUND:
        return NotFoundError(EMAIL_DUMP_NOT_FOUND)
    return ServiceUnavailableError(
        EMAIL_DUMP_RATE_LIMITED
        if status_code == STATUS_TOO_MANY_REQUESTS
        else EMAIL_DUMP_UNAVAILABLE
    )


async def fetch_origin_ips(
    case_id: int,
    query: EmailDumpOriginIpQuery,
    access_token: str,
) -> list[EmailOriginIpRecord]:
    url = build_origin_ips_url(case_id)
    params = query.to_forward_params()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.EMAIL_DUMP_TIMEOUT_SECONDS)
        ) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.TimeoutException as exc:
        logger.warning("Email Dump request timed out | case_id=%s | error=%s", case_id, exc)
        raise GatewayTimeoutError(EMAIL_DUMP_TIMEOUT) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "Email Dump request failed | case_id=%s | error=%s", case_id, type(exc).__name__
        )
        raise ServiceUnavailableError(EMAIL_DUMP_UNAVAILABLE) from exc

    if response.status_code != 200:
        logger.warning(
            "Email Dump returned an error | case_id=%s | status=%s",
            case_id,
            response.status_code,
        )
        raise _provider_error(response.status_code)

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("Email Dump returned malformed JSON | case_id=%s", case_id)
        raise ServiceUnavailableError(EMAIL_DUMP_INVALID_RESPONSE) from exc

    try:
        parsed = EmailDumpOriginIpResponse.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "Email Dump returned an unexpected payload | case_id=%s | error=%s", case_id, exc
        )
        raise ServiceUnavailableError(EMAIL_DUMP_INVALID_RESPONSE) from exc

    logger.info(
        "Email Dump origin IPs fetched | case_id=%s | emails=%s | params=%s",
        case_id,
        len(parsed.data),
        sorted(params),
    )
    return parsed.data


async def _upsert_email(
    case_id: int,
    record: EmailOriginIpRecord,
    origin_ip: OriginIpCount,
    layer_id: int | None,
    db,
) -> tuple[EmailRecord, bool]:
    values = {
        "email_address": record.email_address or origin_ip.email_address,
        "count": origin_ip.count,
        "risk_level": record.risk_level,
        "is_suspicious": record.is_suspicious,
        "country": origin_ip.country,
        "isp": origin_ip.isp,
        "first_seen": origin_ip.first_seen,
        "last_seen": origin_ip.last_seen,
    }

    try:
        row = db.scalar(
            select(EmailRecord).where(
                EmailRecord.case_id == case_id,
                EmailRecord.email_id == record.email_id,
                EmailRecord.ip == origin_ip.ip,
                EmailRecord.ip_type == origin_ip.ip_type,
            )
        )
        if row is None:
            row = EmailRecord(
                case_id=case_id,
                email_id=record.email_id,
                ip=origin_ip.ip,
                ip_type=origin_ip.ip_type,
                layer_id=layer_id,
                **values,
            )
            db.add(row)
            db.flush()
            return row, True

        for field, value in values.items():
            setattr(row, field, value)
        row.layer_id = layer_id
        db.flush()
        return row, False
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump email upsert failed | case_id=%s | email_id=%s | ip=%s | "
            "ip_type=%s | error=%s",
            case_id,
            record.email_id,
            origin_ip.ip,
            origin_ip.ip_type,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


async def _delete_stale_email_observations(
    case_id: int,
    record: EmailOriginIpRecord,
    placeable_ips: list[OriginIpCount],
    db,
) -> int:
    reported = {
        (origin_ip.ip, origin_ip.ip_type)
        for origin_ip in record.ips
    }
    try:
        rows = db.scalars(
            select(EmailRecord).where(
                EmailRecord.case_id == case_id,
                EmailRecord.email_id == record.email_id,
            )
        ).all()
        stale = [
            row
            for row in rows
            if (row.ip, row.ip_type) not in reported
        ]
        for row in stale:
            logger.info(
                "Email Dump email observation removed: the provider no longer "
                "reports this IP/role | case_id=%s | email_id=%s | ip=%s | ip_type=%s",
                case_id,
                record.email_id,
                row.ip,
                row.ip_type,
            )
            db.delete(row)
        if stale:
            db.flush()
        return len(stale)
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump stale observation cleanup failed | case_id=%s | "
            "email_id=%s | error=%s",
            case_id,
            record.email_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


async def _upsert_target(
    case_id: int,
    email_id: int,
    target: EmailTargetRef,
    db,
) -> tuple[EmailTarget, bool]:
    try:
        row = db.scalar(
            select(EmailTarget).where(
                EmailTarget.case_id == case_id,
                EmailTarget.target_id == str(target.target_id),
            )
        )
        if row is None:
            row = EmailTarget(
                case_id=case_id,
                target_id=str(target.target_id),
                target_name=target.target_name,
            )
            db.add(row)
            db.flush()
            return row, True

        if target.target_name is not None:
            row.target_name = target.target_name
        db.flush()
        return row, False
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump target upsert failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target.target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


async def _link_target_to_email(case_id: int, target_id: str, email_id: int, db) -> bool:
    try:
        existing = db.scalar(
            select(EmailTargetEmail).where(
                EmailTargetEmail.case_id == case_id,
                EmailTargetEmail.target_id == target_id,
                EmailTargetEmail.email_id == email_id,
            )
        )
        if existing is not None:
            return False

        db.add(
            EmailTargetEmail(
                case_id=case_id,
                target_id=target_id,
                email_id=email_id,
            )
        )
        db.flush()
        return True
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump target/email link failed | case_id=%s | target_id=%s | "
            "email_id=%s | error=%s",
            case_id,
            target_id,
            email_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


async def _upsert_dump(
    case_id: int,
    target_id: str,
    dump: EmailDumpRef,
    db,
) -> tuple[EmailDump, bool]:
    try:
        row = db.scalar(
            select(EmailDump).where(
                EmailDump.case_id == case_id,
                EmailDump.dump_id == str(dump.dump_id),
            )
        )
        if row is None:
            row = EmailDump(
                case_id=case_id,
                dump_id=str(dump.dump_id),
                target_id=str(target_id),
                name=dump.name,
            )
            db.add(row)
            db.flush()
            return row, True

        row.target_id = str(target_id)
        if dump.name is not None:
            row.name = dump.name
        db.flush()
        return row, False
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump dump upsert failed | case_id=%s | dump_id=%s | error=%s",
            case_id,
            dump.dump_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


async def _persist_email_records(
    case_id: int,
    record: EmailOriginIpRecord,
    layer_id: int,
    db,
) -> dict[str, int]:
    counts = {
        "emails_created": 0,
        "emails_updated": 0,
        "emails_removed": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "dumps_created": 0,
        "dumps_updated": 0,
    }

    for origin_ip in record.ips:
        _, created = await _upsert_email(case_id, record, origin_ip, layer_id, db)
        counts["emails_created" if created else "emails_updated"] += 1

    placeable_ips = _placeable_ips(record)
    counts["emails_removed"] += await _delete_stale_email_observations(
        case_id, record, placeable_ips, db
    )

    if record.target_id is not None:
        await _persist_flat_target(case_id, record, counts, db)

    for target in record.targets:
        target_id = str(target.target_id)
        _, created = await _upsert_target(case_id, record.email_id, target, db)
        counts["targets_created" if created else "targets_updated"] += 1
        await _link_target_to_email(case_id, target_id, record.email_id, db)
        for dump in target.dumps:
            _, dump_created = await _upsert_dump(case_id, target_id, dump, db)
            counts["dumps_created" if dump_created else "dumps_updated"] += 1

    return counts


async def _persist_flat_target(
    case_id: int,
    record: EmailOriginIpRecord,
    counts: dict[str, int],
    db,
) -> None:
    target_id = record.target_id
    _, created = await _upsert_target(
        case_id,
        record.email_id,
        EmailTargetRef(target_id=target_id),
        db,
    )
    counts["targets_created" if created else "targets_updated"] += 1
    await _link_target_to_email(case_id, target_id, record.email_id, db)

    if record.dump_id is None:
        return

    _, dump_created = await _upsert_dump(
        case_id,
        target_id,
        EmailDumpRef(dump_id=record.dump_id),
        db,
    )
    counts["dumps_created" if dump_created else "dumps_updated"] += 1


def _is_valid_latitude(latitude: float | None) -> bool:
    return (
        latitude is not None
        and math.isfinite(latitude)
        and -90 <= latitude <= 90
    )


def _is_valid_longitude(longitude: float | None) -> bool:
    return (
        longitude is not None
        and math.isfinite(longitude)
        and -180 <= longitude <= 180
    )


def _placeable_ips(record: EmailOriginIpRecord) -> list[OriginIpCount]:
    return [
        origin_ip
        for origin_ip in record.ips
        if _is_valid_latitude(origin_ip.latitude)
        and _is_valid_longitude(origin_ip.longitude)
    ]


_ROLE_PRIORITY = (
    "sender_origin_ip",
    "sender_ip",
    "origin_ip",
    "recipient_server_ip",
    "recipient_ip",
)


def _role_rank(ip_type: str) -> int:
    try:
        return _ROLE_PRIORITY.index(ip_type)
    except ValueError:
        return len(_ROLE_PRIORITY)


def _group_ips_by_address(
    placeable_ips: list[OriginIpCount],
) -> dict[str, list[OriginIpCount]]:
    grouped: dict[str, list[OriginIpCount]] = {}
    for origin_ip in placeable_ips:
        grouped.setdefault(origin_ip.ip, []).append(origin_ip)
    for observations in grouped.values():
        observations.sort(key=lambda item: _role_rank(item.ip_type))
    return grouped


def _feature_payload(
    record: EmailOriginIpRecord,
    observations: list[OriginIpCount],
) -> dict:
    primary = observations[0]
    first_seen = [
        observation.first_seen
        for observation in observations
        if observation.first_seen is not None
    ]
    last_seen = [
        observation.last_seen
        for observation in observations
        if observation.last_seen is not None
    ]
    return {
        "name": EMAIL_DUMP_FEATURE_NAME_TEMPLATE.format(ip=primary.ip),
        "geometry_type": "Point",
        "geometry": {
            "type": "Point",
            "coordinates": [primary.longitude, primary.latitude],
        },
        "module_slug": EMAIL_DUMP_MODULE_SLUG,
        "properties": {
            "email_id": record.email_id,
            "ip": primary.ip,
            "ip_type": primary.ip_type,
            "ip_roles": [observation.ip_type for observation in observations],
            "ip_role_count": len(observations),
            "ip_occurrence_total": sum(
                observation.count for observation in observations
            ),
            "count": primary.count,
            "email_address": record.email_address or primary.email_address,
            "risk_level": record.risk_level,
            "is_suspicious": record.is_suspicious,
            "country": primary.country,
            "isp": primary.isp,
            "first_seen": (
                min(first_seen).isoformat() if first_seen else None
            ),
            "last_seen": (
                max(last_seen).isoformat() if last_seen else None
            ),
        },
    }


async def _get_or_create_email_layer(
    case_id: int,
    email_id: int,
    db,
) -> tuple[dict, bool]:
    name = layer_name_for_email(email_id)

    try:
        existing_id = db.scalar(
            select(Layer.id)
            .where(
                Layer.case_id == case_id,
                Layer.name == name,
                Layer.module_slug == EMAIL_DUMP_MODULE_SLUG,
            )
            .limit(1)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump layer lookup failed | case_id=%s | name=%s | error=%s",
            case_id,
            name,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc

    if existing_id is not None:
        return await get_layer(existing_id, db), False

    result = await create_layer(
        {
            "case_id": case_id,
            "name": name,
            "layer_type": EMAIL_DUMP_LAYER_TYPE,
            "module_slug": EMAIL_DUMP_MODULE_SLUG,
            "visible": True,
        },
        db,
    )
    return await get_layer(result["layer_id"], db), True


async def _existing_features_by_ip(
    case_id: int,
    layer_id: int,
    email_id: int,
    db,
) -> dict[str, Feature]:
    try:
        features = db.scalars(
            select(Feature).where(
                Feature.case_id == case_id,
                Feature.layer_id == layer_id,
                Feature.module_slug == EMAIL_DUMP_MODULE_SLUG,
                Feature.properties["email_id"].as_string() == str(email_id),
            )
        ).all()
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump feature lookup failed | case_id=%s | layer_id=%s | "
            "email_id=%s | error=%s",
            case_id,
            layer_id,
            email_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc

    by_ip: dict[str, Feature] = {}
    for feature in features:
        properties = feature.properties
        if not isinstance(properties, dict):
            continue
        ip = properties.get("ip")
        if isinstance(ip, str):
            by_ip[ip] = feature
    return by_ip


def _feature_needs_update(feature: Feature, payload: dict) -> bool:
    if feature.name != payload["name"]:
        return True
    if feature.geometry_type != payload["geometry_type"]:
        return True
    return feature.properties != payload["properties"]


async def _refresh_feature(feature: Feature, payload: dict, db) -> bool:
    try:
        feature.name = payload["name"]
        feature.geometry_type = payload["geometry_type"]
        feature.properties = payload["properties"]
        feature.geom = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(json.dumps(payload["geometry"])), 4326
        )
        feature.updated_at = func.now()
        db.flush()
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump feature refresh failed | feature_id=%s | error=%s",
            feature.id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc
    return True


async def _remove_feature(feature: Feature, db) -> bool:
    try:
        db.delete(feature)
        db.flush()
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump feature removal failed | feature_id=%s | error=%s",
            feature.id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc
    return True


async def _broadcast_layer_created(layer: dict) -> None:
    message = {
        "event": "layer.created",
        "case_id": layer["case_id"],
        "layer": layer,
    }
    await layer_connection_manager.broadcast(layer["case_id"], message)
    await feature_connection_manager.broadcast(layer["case_id"], message)


async def _broadcast_features_created(
    case_id: int,
    layer_id: int,
    features: list[dict],
) -> None:
    if not features:
        return
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.batch_created",
            "case_id": case_id,
            "layer_id": layer_id,
            "count": len(features),
            "features": features,
        },
    )


async def _broadcast_features_updated(
    case_id: int,
    layer_id: int,
    features: list[dict],
) -> None:
    if not features:
        return
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.batch_updated",
            "case_id": case_id,
            "layer_id": layer_id,
            "count": len(features),
            "features": features,
        },
    )


async def _broadcast_features_deleted(
    case_id: int,
    layer_id: int,
    feature_ids: list[int],
) -> None:
    if not feature_ids:
        return
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.batch_deleted",
            "case_id": case_id,
            "layer_id": layer_id,
            "count": len(feature_ids),
            "feature_ids": feature_ids,
        },
    )


def _case_totals(case_id: int, db) -> dict[str, int]:
    try:
        targets = db.scalar(
            select(func.count())
            .select_from(EmailTarget)
            .where(EmailTarget.case_id == case_id)
        )
        dumps = db.scalar(
            select(func.count())
            .select_from(EmailDump)
            .where(EmailDump.case_id == case_id)
        )
        ips = db.scalar(
            select(func.count())
            .select_from(EmailRecord)
            .where(EmailRecord.case_id == case_id)
        )
        emails = db.scalar(
            select(func.count(distinct(EmailRecord.email_id))).where(
                EmailRecord.case_id == case_id
            )
        )
        features = db.scalar(
            select(func.count())
            .select_from(Feature)
            .where(
                Feature.case_id == case_id,
                Feature.module_slug == EMAIL_DUMP_MODULE_SLUG,
            )
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump totals failed | case_id=%s | error=%s",
            case_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc

    return {
        "targets": targets or 0,
        "dumps": dumps or 0,
        "emails": emails or 0,
        "ips": ips or 0,
        "features": features or 0,
    }


async def import_origin_ips(
    case_id: int,
    query: EmailDumpOriginIpQuery,
    access_token: str,
    db,
    created_by: int | None = None,
) -> EmailDumpOriginIpImportResponse:
    records = await fetch_origin_ips(case_id, query, access_token)

    layers: list[dict] = []
    layers_created = 0
    layers_reused = 0
    features_created = 0
    features_updated = 0
    features_unchanged = 0
    features_removed = 0
    skipped_coordinates = 0

    counts = {
        "emails_created": 0,
        "emails_updated": 0,
        "emails_removed": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "dumps_created": 0,
        "dumps_updated": 0,
    }

    for record in records:
        placeable_ips = _placeable_ips(record)
        dropped = len(record.ips) - len(placeable_ips)
        if dropped:
            skipped_coordinates += dropped
            logger.info(
                "Email Dump IP skipped: missing or invalid coordinates | "
                "case_id=%s | email_id=%s | skipped=%s",
                case_id,
                record.email_id,
                dropped,
            )
        if not placeable_ips:
            logger.info(
                "Email Dump email skipped: no usable coordinates, so it would "
                "create an empty layer | case_id=%s | email_id=%s | ips=%s",
                case_id,
                record.email_id,
                len(record.ips),
            )
            continue

        layer, layer_created = await _get_or_create_email_layer(
            case_id, record.email_id, db
        )
        layer_id = layer["id"]

        record_counts = await _persist_email_records(case_id, record, layer_id, db)
        for key, value in record_counts.items():
            counts[key] += value

        layers.append(layer)
        if layer_created:
            layers_created += 1
            await _broadcast_layer_created(layer)
        else:
            layers_reused += 1

        existing = await _existing_features_by_ip(
            case_id, layer_id, record.email_id, db
        )
        payloads = {
            ip: _feature_payload(record, observations)
            for ip, observations in _group_ips_by_address(placeable_ips).items()
        }

        refreshed: list[dict] = []
        for ip, feature in existing.items():
            payload = payloads.get(ip)
            if payload is None:
                await _remove_feature(feature, db)
                features_removed += 1
                continue
            if _feature_needs_update(feature, payload):
                await _refresh_feature(feature, payload, db)
                refreshed.append(
                    {
                        "id": feature.id,
                        "layer_id": layer_id,
                        "properties": payload["properties"],
                        "geometry": payload["geometry"],
                        "geometry_type": payload["geometry_type"],
                        "name": payload["name"],
                    }
                )
                features_updated += 1
            else:
                features_unchanged += 1

        if refreshed:
            await _broadcast_features_updated(case_id, layer_id, refreshed)

        pending = [
            payload
            for ip, payload in payloads.items()
            if ip not in existing
        ]
        if pending:
            created = create_features_batch(
                pending,
                case_id,
                layer_id,
                db,
                created_by=created_by,
                module_slug=EMAIL_DUMP_MODULE_SLUG,
            )
            features_created += len(created)
            await _broadcast_features_created(case_id, layer_id, created)

        await _broadcast_features_deleted(
            case_id,
            layer_id,
            [
                feature.id
                for ip, feature in existing.items()
                if ip not in payloads
            ],
        )

    logger.info(
        "Email Dump origin IPs imported | case_id=%s | layers_created=%s | "
        "layers_reused=%s | features_created=%s | features_updated=%s | "
        "features_unchanged=%s | features_removed=%s | "
        "skipped_coordinates=%s | emails_created=%s | emails_updated=%s | "
        "emails_removed=%s | targets_created=%s | targets_updated=%s | "
        "dumps_created=%s | dumps_updated=%s",
        case_id,
        layers_created,
        layers_reused,
        features_created,
        features_updated,
        features_unchanged,
        features_removed,
        skipped_coordinates,
        counts["emails_created"],
        counts["emails_updated"],
        counts["emails_removed"],
        counts["targets_created"],
        counts["targets_updated"],
        counts["dumps_created"],
        counts["dumps_updated"],
    )

    totals = _case_totals(case_id, db)
    logger.info(
        "Email Dump case totals | case_id=%s | targets=%s | dumps=%s | emails=%s | "
        "ips=%s | features=%s",
        case_id,
        totals["targets"],
        totals["dumps"],
        totals["emails"],
        totals["ips"],
        totals["features"],
    )

    return EmailDumpOriginIpImportResponse(
        case_id=case_id,
        layers=layers,
        **totals,
    )
