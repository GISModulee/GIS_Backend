import math
from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator

from schemas.layer_schema import LayerResponse
from utils.exceptions import UnprocessableEntityError


class EmailDumpOriginIpQuery(BaseModel):

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
        return {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }


def _identifier(value: Any) -> str:
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
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class EmailDumpRef(BaseModel):

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

    target_id: str
    target_name: str | None = None
    dumps: list[EmailDumpRef] = Field(default_factory=list)

    @field_validator("target_id", mode="before")
    @classmethod
    def _coerce_target_id(cls, value: Any) -> str:
        return _identifier(value)


class OriginIpCount(BaseModel):

    ip: str
    ip_type: str = "origin"
    count: int = Field(default=0, validation_alias=AliasChoices("count", "total"))
    is_recent: bool = False
    mismatch_count: int = 0
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

    email_id: int
    email_address: str | None = None
    target_id: str | None = None
    dump_id: str | None = None
    risk_level: str | None = None
    is_suspicious: bool = False
    total: int = 0
    mismatch_count: int = 0
    ips: list[OriginIpCount] = Field(default_factory=list)
    targets: list[EmailTargetRef] = Field(default_factory=list)

    @field_validator("is_suspicious", mode="before")
    @classmethod
    def _validate_is_suspicious(cls, value: Any) -> bool:
        return bool(value) if value is not None else False

    @field_validator("target_id", "dump_id", mode="before")
    @classmethod
    def _coerce_identifier(cls, value: Any) -> str | None:
        return _identifier(value) if value is not None else None


class EmailDumpOriginIpResponse(BaseModel):

    success: bool = True
    message: str | None = None
    data: list[EmailOriginIpRecord]
    meta: dict[str, Any] | None = None


MAX_TARGET_IDS_PER_REQUEST = 25


def parse_target_ids(raw: str) -> list[str]:
    ids: list[str] = []
    for segment in raw.split(","):
        value = segment.strip()
        if value and value not in ids:
            ids.append(value)

    if not ids:
        raise UnprocessableEntityError(
            "target_id must name at least one target, e.g. target_id=1 or target_id=1,2"
        )
    if len(ids) > MAX_TARGET_IDS_PER_REQUEST:
        raise UnprocessableEntityError(
            f"target_id may name at most {MAX_TARGET_IDS_PER_REQUEST} targets, "
            f"got {len(ids)}"
        )
    return ids


class EmailDumpDumpsQuery(BaseModel):

    target_id: str

    @field_validator("target_id")
    @classmethod
    def _reject_empty_selection(cls, value: str) -> str:
        parse_target_ids(value)
        return value

    @property
    def target_ids(self) -> list[str]:
        return parse_target_ids(self.target_id)


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_datetime(value: Any) -> datetime | None:
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

    target_id: int
    target_email: str
    dump_count: int = 0
    dump_ids: list[str] = Field(default_factory=list)
    dump_statuses: dict[str, str] = Field(default_factory=dict)
    report_id: int | None = None


class EmailDumpTargetsResponse(BaseModel):

    success: bool = True
    case_id: int
    targets: list[EmailTargetSummary]
    targets_count: int = 0


class EmailDumpListResponse(BaseModel):

    success: bool = True
    case_id: int
    target_ids: list[str]
    dumps: list[EmailDumpRef]
    dumps_created: int = 0
    dumps_updated: int = 0
    from_cache: bool = False


class EmailDumpOriginIpImportResponse(BaseModel):
    success: bool = True
    case_id: int
    targets: int
    dumps: int
    emails: int
    ips: int
    features: int
    layers: list[LayerResponse]
