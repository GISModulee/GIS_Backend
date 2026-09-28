import math

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import Feature, Layer
from schemas.email_dump_schema import (
    EmailDumpOriginIpImportResponse,
    EmailDumpOriginIpQuery,
    EmailDumpOriginIpResponse,
    EmailOriginIpRecord,
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

    for record in records:
        layer, layer_created = await _get_or_create_email_layer(
            case_id, record.email_id, db
        )
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
        "skipped_coordinates=%s",
        case_id,
        layers_created,
        layers_reused,
        features_created,
        features_reused,
        skipped_coordinates,
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
    )
