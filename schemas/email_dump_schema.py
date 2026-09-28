import math
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from schemas.layer_schema import LayerResponse
from utils.constants import EMAIL_DUMP_MODULE_SLUG


# ===================================================
# UPSTREAM EMAIL DUMP REQUEST
# ===================================================
# Every documented Email Dump query parameter is optional; only the
# ones the caller actually supplied are forwarded upstream.

class EmailDumpOriginIpQuery(BaseModel):
    """Query parameters accepted by the Email Dump origin-IP endpoint.

    `target_id` and `dump_id` stay as strings so the value supplied by
    the caller is forwarded verbatim — the GIS backend must not assume
    the provider's identifier type.
    """

    view_type: str | None = None
    target_id: str | None = None
    dump_id: str | None = None
    ip_type: str | None = None
    limit: int | None = Field(default=None, ge=1)
    keyword: str | None = None
    isp: str | None = None
    country: str | None = None
    risk_level: str | None = None
    is_suspicious: bool | None = None

    def to_forward_params(self) -> dict[str, Any]:
        """Return only the parameters that were actually provided."""
        return {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }


# ===================================================
# UPSTREAM EMAIL DUMP RESPONSE
# ===================================================
# The provider response is validated before anything reaches the
# database: arbitrary provider JSON is never persisted as-is.


def _optional_float(value: Any) -> float | None:
    """Coerce a provider coordinate to float, or None when unusable.

    A malformed coordinate is treated as a missing one (and counted as
    skipped) instead of failing the whole import.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class OriginIpCount(BaseModel):
    """One IP address occurrence reported for an email."""

    ip: str
    ip_type: str = "origin"
    count: int = 0
    email_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    isp: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _validate_coordinate(cls, value: Any) -> float | None:
        return _optional_float(value)


class EmailOriginIpRecord(BaseModel):
    """One email and the IP addresses observed for it."""

    email_id: int
    risk_level: str | None = None
    is_suspicious: bool = False
    ips: list[OriginIpCount] = Field(default_factory=list)

    @field_validator("is_suspicious", mode="before")
    @classmethod
    def _validate_is_suspicious(cls, value: Any) -> bool:
        return bool(value) if value is not None else False


class EmailDumpOriginIpResponse(BaseModel):
    """Envelope returned by the Email Dump origin-IP endpoint.

    `data` is required: a payload without it is an invalid provider
    response, not an empty result.
    """

    success: bool = True
    message: str | None = None
    data: list[EmailOriginIpRecord]
    meta: dict[str, Any] | None = None


# ===================================================
# GIS RESPONSE
# ===================================================
# A GIS-specific summary. The raw provider payload is never returned
# to the frontend.

class EmailDumpOriginIpImportResponse(BaseModel):
    success: bool = True
    case_id: int
    module_slug: str = EMAIL_DUMP_MODULE_SLUG
    layers_created: int
    layers_reused: int
    features_created: int
    features_reused: int
    skipped_coordinates: int
    layers: list[LayerResponse]
