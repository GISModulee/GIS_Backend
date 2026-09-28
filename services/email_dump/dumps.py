"""Email Dump per-case dump listing.

GIS is a proxy for the external Email Dump Backend; it owns no dump data
of its own. This module calls the provider's per-case dumps endpoint,
validates its response, caches the result in the `email_dumps` table, and
returns a normalised list to the frontend.

The frontend uses this to populate the dump dropdown when a target is
selected. Both listings are also written to the normalised tables, so
`email_targets` holds every target the provider reports -- whether it
came from this listing or from the origin-IP import -- and `email_dumps`
references those rows on `(case_id, target_id)`. That is what lets a dump
be cached for a target the user picked but never imported.
"""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import EmailDump, EmailTarget
from schemas.email_dump_schema import (
    EmailDumpListResponse,
    EmailDumpRef,
    EmailDumpTargetsResponse,
    EmailTargetSummary,
    _optional_datetime,
    _optional_int,
)
from utils.config import settings
from utils.constants import (
    EMAIL_DUMP_DUMPS_FETCH_FAILED,
    EMAIL_DUMP_DUMPS_PATH,
    EMAIL_DUMP_INVALID_DUMPS_RESPONSE,
    EMAIL_DUMP_INVALID_TARGETS_RESPONSE,
    EMAIL_DUMP_NOT_CONFIGURED,
    EMAIL_DUMP_RATE_LIMITED,
    EMAIL_DUMP_TARGETS_PREFIX_PATH,
    EMAIL_DUMP_TARGETS_FETCH_FAILED,
    EMAIL_DUMP_TARGET_NOT_FOUND,
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


def _base_url() -> str:
    """The configured provider host, without a trailing slash."""
    base_url = (settings.EMAIL_DUMP_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("Email Dump base URL is not configured")
        raise ServiceUnavailableError(EMAIL_DUMP_NOT_CONFIGURED)
    return base_url


def build_dumps_url(case_id: int) -> str:
    """Build the provider dumps URL from the configured base URL.

    Same contract as the origin-IP URL builder: the host comes from
    settings and only the path GIS is allowed to consume is hard-coded.
    The case id is appended, matching the provider's `/single/{case_id}`
    convention.
    """
    return f"{_base_url()}{EMAIL_DUMP_DUMPS_PATH}/{case_id}"


def build_targets_url(case_id: int) -> str:
    """Build the provider per-case target list URL.

    The provider documents this as `/api/cases/{case_id}/targets`, so the
    prefix is a constant and only the case id and the leaf are appended.
    """
    return f"{_base_url()}{EMAIL_DUMP_TARGETS_PREFIX_PATH}/{case_id}/targets"


def _provider_error(status_code: int) -> AppException:
    """Map an upstream failure onto a clean application error.

    The provider's error body is never forwarded to the client.
    """
    if status_code in (STATUS_UNAUTHORIZED, STATUS_FORBIDDEN):
        return UnauthorizedError(EMAIL_DUMP_UNAUTHORIZED)
    if status_code == STATUS_NOT_FOUND:
        return NotFoundError(EMAIL_DUMP_TARGET_NOT_FOUND)
    return ServiceUnavailableError(
        EMAIL_DUMP_RATE_LIMITED
        if status_code == STATUS_TOO_MANY_REQUESTS
        else EMAIL_DUMP_UNAVAILABLE
    )


def _normalise(item: dict) -> EmailDumpRef | None:
    """Read one provider dump entry into a model.

    Returns None when the entry carries no usable identifier, since a row
    without one cannot be upserted. Counters and dates are individually
    optional: a malformed value becomes None rather than failing the
    whole listing, because the identifiers are still worth returning.
    """
    dump_id = item.get("dump_id")
    if dump_id is None or isinstance(dump_id, (dict, list, bool)):
        return None
    dump_id = str(dump_id).strip()
    if not dump_id:
        return None

    return EmailDumpRef(
        dump_id=dump_id,
        # Upstream sends no name, so `name` stays None and the frontend
        # falls back to the counters for its dropdown label.
        name=item.get("name") if isinstance(item.get("name"), str) else None,
        total_emails=_optional_int(item.get("total_emails")),
        malicious_count=_optional_int(item.get("malicious_count")),
        unique_senders=_optional_int(item.get("unique_senders")),
        unique_recipients=_optional_int(item.get("unique_recipients")),
        start_date=_optional_datetime(item.get("start_date")),
        end_date=_optional_datetime(item.get("end_date")),
        created_at=_optional_datetime(item.get("created_at")),
    )


async def _get(
    url: str,
    case_id: int,
    target_id: str | None,
    access_token: str,
    invalid_message: str,
) -> Any:
    """Shared GET against the provider with GIS-owned error mapping.

    The caller's bearer token is forwarded so Email Dump applies its own
    authorization; GIS never mints or stores provider credentials. The
    provider's error body is never returned to the client.
    """
    params = {"target_id": target_id} if target_id is not None else None

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
        logger.warning(
            "Email Dump request timed out | url=%s | error=%s", url, exc
        )
        raise GatewayTimeoutError(EMAIL_DUMP_TIMEOUT) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "Email Dump request failed | url=%s | error=%s", url, type(exc).__name__
        )
        raise ServiceUnavailableError(EMAIL_DUMP_UNAVAILABLE) from exc

    if response.status_code != 200:
        logger.warning(
            "Email Dump returned an error | url=%s | target_id=%s | status=%s",
            url,
            target_id,
            response.status_code,
        )
        raise _provider_error(response.status_code)

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("Email Dump returned malformed JSON | url=%s", url)
        raise ServiceUnavailableError(invalid_message) from exc


def _extract_list(payload: Any, message: str, case_id: int, what: str) -> list[dict]:
    """Pull the item list out of the provider's `{"success","data"}`
    envelope.

    `data` is the documented key and is required: a payload without it is
    an invalid provider response, not an empty result. A bare list is also
    accepted, since that is the only other shape observed.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]

    observed = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
    logger.warning(
        "Email Dump %s payload had no usable data list | case_id=%s | keys=%s",
        what,
        case_id,
        observed,
    )
    raise ServiceUnavailableError(message)


async def fetch_targets(
    case_id: int,
    access_token: str,
) -> list[EmailTargetSummary]:
    """List the targets the provider knows about for a case.

    This is the route the frontend uses to populate its target list. The
    provider already includes each target's `dump_ids`, so a frontend can
    fill a dump dropdown from this response alone without the separate
    dumps call.
    """
    url = build_targets_url(case_id)
    payload = await _get(
        url,
        case_id,
        target_id=None,
        access_token=access_token,
        invalid_message=EMAIL_DUMP_INVALID_TARGETS_RESPONSE,
    )
    items = _extract_list(
        payload, EMAIL_DUMP_INVALID_TARGETS_RESPONSE, case_id, "targets"
    )

    targets: list[EmailTargetSummary] = []
    for item in items:
        # target_id is documented as an integer, but a provider may send
        # it as a string; both are accepted rather than dropping the row.
        target_id = _optional_int(item.get("target_id"))
        target_email = item.get("target_email")
        if target_id is None or not isinstance(target_email, str):
            logger.warning(
                "Email Dump target entry missing target_id/target_email, skipping | case_id=%s",
                case_id,
            )
            continue

        dump_ids = [
            str(value)
            for value in (item.get("dump_ids") or [])
            if isinstance(value, (str, int)) and not isinstance(value, bool)
        ]
        raw_statuses = item.get("dump_statuses")
        statuses = (
            {str(k): str(v) for k, v in raw_statuses.items()}
            if isinstance(raw_statuses, dict)
            else {}
        )

        targets.append(
            EmailTargetSummary(
                target_id=target_id,
                target_email=target_email,
                dump_count=_optional_int(item.get("dump_count")) or len(dump_ids),
                dump_ids=dump_ids,
                dump_statuses=statuses,
                report_id=_optional_int(item.get("report_id")),
            )
        )

    logger.info("Email Dump targets fetched | case_id=%s | targets=%s", case_id, len(targets))
    return targets


def _persist_targets(
    case_id: int,
    targets: list[EmailTargetSummary],
    db,
) -> tuple[int, int]:
    """Store the provider's target listing in `email_targets`.

    Returns (created, updated). Rows are keyed on (case_id, target_id),
    the provider's own identifiers, so re-listing refreshes the same rows
    instead of accumulating duplicates.

    `email_id` is left alone on update. The listing does not say which
    email reported a target, and the origin-IP import does, so the import
    stays the authority there and a blank written here is filled in later
    rather than being overwritten with nothing.

    `target_name` is only set when the row is created, for the same
    reason: the listing's `target_email` is a fallback label for a target
    nobody has imported yet, while the import's name is the real one and
    should not be replaced by an address.
    """
    created = 0
    updated = 0

    try:
        existing = {
            (row.case_id, row.target_id): row
            for row in db.scalars(
                select(EmailTarget).where(EmailTarget.case_id == case_id)
            ).all()
        }

        for target in targets:
            # The listing documents target_id as an integer while the
            # column is text, so it is normalised the same way the
            # provider's other identifiers are.
            target_id = str(target.target_id)
            row = existing.get((case_id, target_id))
            if row is None:
                db.add(
                    EmailTarget(
                        case_id=case_id,
                        target_id=target_id,
                        target_name=target.target_email,
                    )
                )
                created += 1
            elif row.email_id is None or row.target_name is None:
                # A row from an earlier listing that the import has not
                # enriched yet. Filling the gaps counts as a change.
                if row.target_name is None:
                    row.target_name = target.target_email
                updated += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Email Dump targets cache write failed | case_id=%s | error=%s",
            case_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_TARGETS_FETCH_FAILED) from exc

    return created, updated


async def list_targets(
    case_id: int,
    access_token: str,
    db,
) -> EmailDumpTargetsResponse:
    """List the targets for a case, for the frontend's target list.

    The provider is called on every request, so the response reflects the
    provider rather than a local cache, and the result is also written to
    `email_targets`. Saving every listing means a target picked from the
    dropdown is a real row, which is what lets the dumps route cache its
    dumps afterwards: `email_dumps` has a foreign key to `email_targets`,
    so a dump cannot be stored for a target that has no row.

    A target stored this way has a null `email_id`, because the listing
    does not say which email reported it. Its layer, if one is needed, is
    reached through the email that the import later records.
    """
    targets = await fetch_targets(case_id, access_token)
    created, updated = _persist_targets(case_id, targets, db)

    if created or updated:
        logger.info(
            "Email Dump targets stored | case_id=%s | created=%s | updated=%s",
            case_id,
            created,
            updated,
        )

    return EmailDumpTargetsResponse(
        case_id=case_id,
        targets=targets,
        targets_count=len(targets),
    )


async def fetch_dumps(
    case_id: int,
    target_id: str,
    access_token: str,
) -> list[EmailDumpRef]:
    """Call the provider dumps endpoint and normalise its response.

    `target_id` is optional upstream (the provider documents it as an
    untyped query parameter), so this returns every dump in the case when
    the caller supplies an empty target filter.
    """
    url = build_dumps_url(case_id)
    payload = await _get(
        url,
        case_id,
        target_id=target_id or None,
        access_token=access_token,
        invalid_message=EMAIL_DUMP_INVALID_DUMPS_RESPONSE,
    )
    items = _extract_list(payload, EMAIL_DUMP_INVALID_DUMPS_RESPONSE, case_id, "dumps")

    dumps: list[EmailDumpRef] = []
    for item in items:
        normalised = _normalise(item)
        if normalised is not None:
            dumps.append(normalised)

    logger.info(
        "Email Dump dumps fetched | case_id=%s | target_id=%s | dumps=%s",
        case_id,
        target_id,
        len(dumps),
    )
    return dumps


def resolve_target_row(
    case_id: int,
    target_id: str,
    db,
) -> EmailTarget | None:
    """Find the imported `email_targets` row for a provider target_id.

    Returns None when the target has not been imported, which is the
    normal case for a target listed by the provider's case-targets
    endpoint: those rows come from the provider's own case view and are
    not the ones the origin-IP import writes.

    The comparison is done on the string form, because the column is a
    string while the provider documents `target_id` as an integer; a
    numeric target id would otherwise never match.
    """
    try:
        row = db.scalar(
            select(EmailTarget).where(
                EmailTarget.case_id == case_id,
                EmailTarget.target_id == str(target_id),
            )
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump target lookup failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    if row is None:
        logger.info(
            "Email Dump target has not been imported for this case | case_id=%s | target_id=%s",
            case_id,
            target_id,
        )
    return row


def _cached_dumps(case_id: int, target_id: str, db) -> list[EmailDumpRef]:
    """Dumps already stored for a target, in insertion order."""
    try:
        rows = db.scalars(
            select(EmailDump)
            .where(
                EmailDump.case_id == case_id,
                EmailDump.target_id == str(target_id),
            )
            .order_by(EmailDump.dump_id)
        ).all()
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump cached dumps lookup failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    return [
        EmailDumpRef(
            dump_id=row.dump_id,
            name=row.name,
            total_emails=row.total_emails,
            malicious_count=row.malicious_count,
            unique_senders=row.unique_senders,
            unique_recipients=row.unique_recipients,
            start_date=row.start_date,
            end_date=row.end_date,
            created_at=row.provider_created_at,
        )
        for row in rows
    ]


def _cache_dumps(
    case_id: int,
    target_id: str,
    dumps: list[EmailDumpRef],
    db,
) -> tuple[int, int]:
    """Upsert the fetched dumps into `email_dumps`.

    Returns (created, updated). The key is (case_id, dump_id), so a
    repeat listing refreshes the counters in place instead of
    duplicating rows. Dumps the provider no longer returns are left
    alone: a partial upstream list should not delete history.
    """
    created = 0
    updated = 0

    # The provider's own values, keyed so a change to any of them counts
    # as an update.
    def _values(dump: EmailDumpRef) -> dict:
        return {
            "name": dump.name,
            "total_emails": dump.total_emails,
            "malicious_count": dump.malicious_count,
            "unique_senders": dump.unique_senders,
            "unique_recipients": dump.unique_recipients,
            "start_date": dump.start_date,
            "end_date": dump.end_date,
            "provider_created_at": dump.created_at,
        }

    try:
        existing = {
            row.dump_id: row
            for row in db.scalars(
                select(EmailDump).where(
                    EmailDump.case_id == case_id,
                    EmailDump.target_id == str(target_id),
                )
            ).all()
        }

        for dump in dumps:
            values = _values(dump)
            row = existing.get(dump.dump_id)
            if row is None:
                db.add(
                    EmailDump(
                        case_id=case_id,
                        target_id=str(target_id),
                        dump_id=str(dump.dump_id),
                        **values,
                    )
                )
                created += 1
            else:
                # The dump is keyed by itself, so its target can change:
                # the provider may report the same dump under another
                # target.
                changed = row.target_id != str(target_id)
                row.target_id = str(target_id)
                for field, value in values.items():
                    # A field the listing could not fill must not blank a
                    # value the import stored. The provider's dump listing
                    # carries no name at all, so writing its null would
                    # erase the only label a dump has.
                    if value is None:
                        continue
                    if getattr(row, field) != value:
                        setattr(row, field, value)
                        changed = True
                if changed:
                    updated += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Email Dump dumps cache write failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    return created, updated


async def list_dumps(
    case_id: int,
    target_id: str,
    access_token: str,
    db,
) -> EmailDumpListResponse:
    """List the dumps available for one target.

    The provider is the source of truth and is called on every request.
    The result is also cached in `email_dumps`. The target row is written
    by the case-targets listing, so a target the user picked from the
    dropdown already has one; a target that somehow does not is still
    answered from the provider, just uncached, because `email_dumps` has a
    foreign key to `email_targets` and cannot hold a dump for a target
    that has no row.
    """
    target_row = resolve_target_row(case_id, target_id, db)

    dumps = await fetch_dumps(case_id, target_id, access_token)

    if target_row is None:
        logger.info(
            "Email Dump dumps not cached, target not imported | case_id=%s | target_id=%s",
            case_id,
            target_id,
        )
        return EmailDumpListResponse(
            case_id=case_id,
            target_id=target_id,
            dumps=dumps,
        )

    created, updated = _cache_dumps(case_id, target_id, dumps, db)

    if not dumps:
        # An empty upstream list is a valid answer, not an error, but the
        # previously cached rows are the more useful thing to show.
        cached = _cached_dumps(case_id, target_id, db)
        if cached:
            logger.info(
                "Email Dump returned no dumps, serving cached list | case_id=%s | target_id=%s",
                case_id,
                target_id,
            )
            return EmailDumpListResponse(
                case_id=case_id,
                target_id=target_id,
                dumps=cached,
                from_cache=True,
            )

    return EmailDumpListResponse(
        case_id=case_id,
        target_id=target_id,
        dumps=dumps,
        dumps_created=created,
        dumps_updated=updated,
    )
