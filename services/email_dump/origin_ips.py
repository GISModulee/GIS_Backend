import math

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import EmailDump, EmailRecord, EmailTarget, Feature, Layer
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


# ===================================================
# EMAIL DUMP -> GIS INTEGRATION
# ===================================================
# GIS is the integration/proxy layer only. Email analysis, email
# records, risk analysis, origin-IP analysis, and Email Dump
# authentication stay in the external Email Dump Backend; this module
# calls the single documented origin-IP endpoint, validates its
# response, and converts it into GIS layers and features.
#
# Mapping (deterministic, so repeat imports are idempotent):
#   email_id  -> one case-scoped layer named "Email {email_id}"
#   valid ip  -> one Point feature named "IP {ip}" in that layer


def build_origin_ips_url(case_id: int) -> str:
    """Build the provider URL from the configured base URL.

    The host is never hard-coded here; only the path segment GIS is
    allowed to consume is. An unset base URL is a configuration error
    for this route only — the application still starts without it.
    """
    base_url = (settings.EMAIL_DUMP_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("Email Dump base URL is not configured")
        raise ServiceUnavailableError(EMAIL_DUMP_NOT_CONFIGURED)
    return f"{base_url}{EMAIL_DUMP_ORIGIN_IPS_PATH}/{case_id}"


def layer_name_for_email(email_id: int) -> str:
    return EMAIL_DUMP_LAYER_NAME_TEMPLATE.format(email_id=email_id)


def _provider_error(status_code: int) -> AppException:
    """Map an upstream failure onto a clean application error.

    The provider's response body, credentials, and headers are never
    propagated to the client.
    """
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
    """Call the Email Dump origin-IP endpoint and validate the response.

    The caller's bearer token is forwarded to the provider so Email Dump
    applies its own authorization; GIS never mints or stores provider
    credentials.
    """
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
    """Insert or update the `emails` row for one (email_id, ip) pair.

    This is the normalised form of what used to be written only into
    `features.properties`. (case_id, email_id, ip) is the primary key,
    so a re-import updates the existing row instead of duplicating it.
    Returns (row, created).
    """
    values = {
        "email_address": origin_ip.email_address,
        "ip_type": origin_ip.ip_type,
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
            )
        )
        if row is None:
            row = EmailRecord(
                case_id=case_id,
                email_id=record.email_id,
                ip=origin_ip.ip,
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
            "Email Dump email upsert failed | case_id=%s | email_id=%s | ip=%s | error=%s",
            case_id,
            record.email_id,
            origin_ip.ip,
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
    """Insert or update one `email_targets` row for an email.

    Keyed on (case_id, target_id), the provider's own identifiers, with
    `email_id` recording which email reported it.

    The same row is also written by the case-targets listing, which
    leaves `email_id` null. An import is the more specific source, so it
    fills the blank in rather than skipping a target it has just seen
    attributed to it.
    """
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
                email_id=email_id,
                target_name=target.target_name,
            )
            db.add(row)
            db.flush()
            return row, True

        row.email_id = email_id
        # A payload that carries no name must not blank one the listing
        # stored. Both sources are partial about this field, so a missing
        # value is an absence rather than a change.
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


async def _upsert_dump(
    case_id: int,
    target_id: str,
    dump: EmailDumpRef,
    db,
) -> tuple[EmailDump, bool]:
    """Insert or update one `email_dumps` row for a target.

    Keyed on (case_id, dump_id), the provider's own identifiers.
    """
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

        # A dump is keyed by itself, so its target can change: the
        # provider may report the same dump under another target.
        row.target_id = str(target_id)
        # As with a target's name, a payload with no dump name must not
        # blank the one already stored.
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
    """Write the `emails` / `email_targets` / `email_dumps` rows.

    Only `emails` carries a `layer_id`: it is the one table with a row per
    point feature, so it is the one that belongs to a layer. Targets and
    dumps hold no geometry, and their layer is reached through the email
    that reported the target.

    A target belongs to an email rather than to one of its IP
    observations, and `email_targets` is keyed by the provider's own
    identifiers, so a target is written once however many IPs the email
    has: the IP rows do not duplicate it.
    """
    counts = {
        "emails_created": 0,
        "emails_updated": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "dumps_created": 0,
        "dumps_updated": 0,
    }

    for origin_ip in record.ips:
        _, created = await _upsert_email(case_id, record, origin_ip, layer_id, db)
        counts["emails_created" if created else "emails_updated"] += 1

    for target in record.targets:
        target_id = str(target.target_id)
        _, created = await _upsert_target(case_id, record.email_id, target, db)
        counts["targets_created" if created else "targets_updated"] += 1
        for dump in target.dumps:
            _, dump_created = await _upsert_dump(case_id, target_id, dump, db)
            counts["dumps_created" if dump_created else "dumps_updated"] += 1

    return counts


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


def _feature_payload(
    record: EmailOriginIpRecord,
    origin_ip: OriginIpCount,
) -> dict:
    """Build the Point feature for one IP, coordinates as [lon, lat]."""
    return {
        "name": EMAIL_DUMP_FEATURE_NAME_TEMPLATE.format(ip=origin_ip.ip),
        "geometry_type": "Point",
        "geometry": {
            "type": "Point",
            "coordinates": [origin_ip.longitude, origin_ip.latitude],
        },
        "module_slug": EMAIL_DUMP_MODULE_SLUG,
        "properties": {
            "email_id": record.email_id,
            "ip": origin_ip.ip,
            "ip_type": origin_ip.ip_type,
            "count": origin_ip.count,
            "email_address": origin_ip.email_address,
            "risk_level": record.risk_level,
            "is_suspicious": record.is_suspicious,
            "country": origin_ip.country,
            "isp": origin_ip.isp,
            "first_seen": (
                origin_ip.first_seen.isoformat() if origin_ip.first_seen else None
            ),
            "last_seen": (
                origin_ip.last_seen.isoformat() if origin_ip.last_seen else None
            ),
        },
    }


async def _get_or_create_email_layer(
    case_id: int,
    email_id: int,
    db,
) -> tuple[dict, bool]:
    """Reuse or create the case-scoped "Email {email_id}" layer.

    Matching is by case_id + name + module_slug, so the same email_id in
    a different case gets its own layer and a layer is never reused
    across cases.
    """
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


async def _existing_ip_addresses(
    case_id: int,
    layer_id: int,
    email_id: int,
    db,
) -> set[str]:
    """IP addresses already stored in this layer for this email_id."""
    try:
        return {
            row
            for row in db.scalars(
                select(Feature.properties["ip"].as_string()).where(
                    Feature.case_id == case_id,
                    Feature.layer_id == layer_id,
                    Feature.module_slug == EMAIL_DUMP_MODULE_SLUG,
                    Feature.properties["email_id"].as_string() == str(email_id),
                )
            )
            if row
        }
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump feature lookup failed | case_id=%s | layer_id=%s | email_id=%s | error=%s",
            case_id,
            layer_id,
            email_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_IMPORT_FAILED) from exc


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


async def import_origin_ips(
    case_id: int,
    query: EmailDumpOriginIpQuery,
    access_token: str,
    db,
    created_by: int | None = None,
) -> EmailDumpOriginIpImportResponse:
    """Fetch Email Dump origin IPs and persist them as GIS data."""
    records = await fetch_origin_ips(case_id, query, access_token)

    layers: list[dict] = []
    layers_created = 0
    layers_reused = 0
    features_created = 0
    features_reused = 0
    skipped_coordinates = 0

    counts = {
        "emails_created": 0,
        "emails_updated": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "dumps_created": 0,
        "dumps_updated": 0,
    }

    for record in records:
        # The layer is resolved first because the normalised rows record
        # its id. The features below still carry the same data in their
        # properties, so nothing is lost while callers migrate to reading
        # the tables.
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

        already_stored = await _existing_ip_addresses(
            case_id, layer["id"], record.email_id, db
        )

        pending: list[dict] = []
        for origin_ip in record.ips:
            if not (
                _is_valid_latitude(origin_ip.latitude)
                and _is_valid_longitude(origin_ip.longitude)
            ):
                skipped_coordinates += 1
                logger.info(
                    "Email Dump IP skipped: missing or invalid coordinates | "
                    "case_id=%s | email_id=%s | ip=%s",
                    case_id,
                    record.email_id,
                    origin_ip.ip,
                )
                continue

            if origin_ip.ip in already_stored:
                features_reused += 1
                continue

            already_stored.add(origin_ip.ip)
            pending.append(_feature_payload(record, origin_ip))

        if pending:
            created = create_features_batch(
                pending,
                case_id,
                layer["id"],
                db,
                created_by=created_by,
                module_slug=EMAIL_DUMP_MODULE_SLUG,
            )
            features_created += len(created)
            await _broadcast_features_created(case_id, layer["id"], created)

    logger.info(
        "Email Dump origin IPs imported | case_id=%s | layers_created=%s | "
        "layers_reused=%s | features_created=%s | features_reused=%s | "
        "skipped_coordinates=%s | emails_created=%s | emails_updated=%s | "
        "targets_created=%s | targets_updated=%s | dumps_created=%s | "
        "dumps_updated=%s",
        case_id,
        layers_created,
        layers_reused,
        features_created,
        features_reused,
        skipped_coordinates,
        counts["emails_created"],
        counts["emails_updated"],
        counts["targets_created"],
        counts["targets_updated"],
        counts["dumps_created"],
        counts["dumps_updated"],
    )

    return EmailDumpOriginIpImportResponse(
        case_id=case_id,
        module_slug=EMAIL_DUMP_MODULE_SLUG,
        layers_created=layers_created,
        layers_reused=layers_reused,
        features_created=features_created,
        features_reused=features_reused,
        skipped_coordinates=skipped_coordinates,
        layers=layers,
        **counts,
    )
