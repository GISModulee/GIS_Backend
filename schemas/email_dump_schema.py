import math
from datetime import datetime, timezone
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


def _identifier(value: Any) -> str:
    """Coerce a provider identifier to text.

    Provider identifiers are declared as strings on the models because
    the backend must not assume their type, but the provider is not
    consistent about sending them: the case-targets endpoint documents
    `target_id` as an integer while the per-case dumps endpoint leaves it
    untyped, and dump identifiers have been seen both ways. Since these
    values are keys rather than quantities, the integer form is rendered
    as its digits instead of being rejected, and booleans are refused so
    `True` never becomes the id "True".
    """
    if isinstance(value, bool):
        raise ValueError("identifier must not be a boolean")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            raise ValueError("identifier must be integral")
        return str(int(value))
    if isinstance(value, str):
        return value
    raise ValueError("identifier must be a string or a number")


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


class EmailDumpRef(BaseModel):
    """A dump belonging to a target, as sent by the provider.

    Used for the target/dump blocks nested inside the origin-IP payload,
    where the provider sends only an identifier and an optional label.
    The standalone per-case dump listing carries counters as well and is
    read into the same model; see the later definition for the full
    field set.
    """

    dump_id: str
    name: str | None = None
    total_emails: int | None = None
    malicious_count: int | None = None
    unique_senders: int | None = None
    unique_recipients: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime | None = None

    @field_validator("dump_id", mode="before")
    @classmethod
    def _coerce_dump_id(cls, value: Any) -> str:
        return _identifier(value)


class EmailTargetRef(BaseModel):
    """A target identifier reported for an email, with its dumps.

    Declared after EmailDumpRef because it references it.
    """

    target_id: str
    target_name: str | None = None
    dumps: list[EmailDumpRef] = Field(default_factory=list)

    @field_validator("target_id", mode="before")
    @classmethod
    def _coerce_target_id(cls, value: Any) -> str:
        return _identifier(value)


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
    """One email, the IP addresses observed for it, and its targets."""

    email_id: int
    risk_level: str | None = None
    is_suspicious: bool = False
    ips: list[OriginIpCount] = Field(default_factory=list)
    # Empty until the provider sends targets, so existing payloads and
    # existing callers keep working unchanged.
    targets: list[EmailTargetRef] = Field(default_factory=list)

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

class EmailDumpDumpsQuery(BaseModel):
    """Query for the per-case dump listing.

    `target_id` is required. The provider declares it as an untyped
    (query) parameter and returns it as an integer in its target
    listing, so it is accepted as a string and forwarded verbatim: the
    provider owns the identifier's type, GIS does not.
    """

    target_id: str = Field(min_length=1)

    def to_forward_params(self) -> dict[str, Any]:
        return {"target_id": self.target_id}


# ===================================================
# UPSTREAM DUMPS / TARGETS
# ===================================================
# Verified against the provider's own openapi.json, which documents:
#
#   GET /api/dumps/single/{case_id}?target_id=
#     -> {"success", "message", "data": [EmailDumpSchema], "meta"}
#     EmailDumpSchema: dump_id, total_emails, malicious_count,
#       unique_senders, unique_recipients, start_date, end_date,
#       created_at
#
#   GET /api/cases/{case_id}/targets
#     -> {"success", "message", "data": [CaseTargetSchema], "meta"}
#     CaseTargetSchema: target_id (int), target_email, dump_count,
#       dump_ids, dump_statuses, report_id
#
# Note a dump carries no display name upstream, only counters. The
# tolerant extraction below is kept for the identifier alone, so a
# payload variation degrades to a null field instead of a 500.

def _optional_int(value: Any) -> int | None:
    """Coerce a provider counter to int, or None when unusable.

    A malformed count is a missing count: it must not fail the whole
    listing, since the identifiers are still worth returning.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_datetime(value: Any) -> datetime | None:
    """Parse a provider timestamp, or None when absent or unparseable.

    The result is always timezone-naive UTC. The provider sends RFC 3339
    values with an offset, while the dump columns are naive DateTimes, so
    a parsed offset must be converted rather than kept: keeping it makes
    an aware value never compare equal to the stored naive one, which
    would report every dump as changed on every listing.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class EmailTargetSummary(BaseModel):
    """One target in a case, as the provider lists it.

    `dump_ids` is already present upstream, so a frontend can populate a
    dump dropdown from the target list alone without a second call.
    """

    target_id: int
    target_email: str
    dump_count: int = 0
    dump_ids: list[str] = Field(default_factory=list)
    dump_statuses: dict[str, str] = Field(default_factory=dict)
    report_id: int | None = None


class EmailDumpTargetsResponse(BaseModel):
    """Targets in a case, as returned to the frontend."""

    success: bool = True
    case_id: int
    targets: list[EmailTargetSummary]
    targets_count: int = 0


class EmailDumpListResponse(BaseModel):
    """Dumps available for one target, as returned to the frontend."""

    success: bool = True
    case_id: int
    # Echoed as supplied by the caller, so the frontend can correlate the
    # response with the target it asked for.
    target_id: str
    dumps: list[EmailDumpRef]
    # Rows written to / refreshed in the email_dumps table.
    dumps_created: int = 0
    dumps_updated: int = 0
    # True when the dump list came from the local table rather than a
    # fresh upstream call, so the UI can avoid showing a spinner.
    from_cache: bool = False


class EmailDumpOriginIpImportResponse(BaseModel):
    success: bool = True
    case_id: int
    module_slug: str = EMAIL_DUMP_MODULE_SLUG
    layers_created: int
    layers_reused: int
    features_created: int
    features_reused: int
    skipped_coordinates: int
    # Normalised rows written to the emails / email_targets / email_dumps
    # tables, counted as created vs updated on re-import.
    emails_created: int = 0
    emails_updated: int = 0
    targets_created: int = 0
    targets_updated: int = 0
    dumps_created: int = 0
    dumps_updated: int = 0
    layers: list[LayerResponse]
