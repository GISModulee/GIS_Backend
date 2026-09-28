from datetime import datetime
import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from database.database import get_db
from models.model import EmailDump, EmailRecord, EmailTarget, Layer
from schemas.email_dump_schema import (
    EmailDumpOriginIpQuery,
    EmailDumpRef,
    EmailTargetRef,
)
from services.email_dump import origin_ips
from services.email_dump.dumps import (
    build_dumps_url,
    build_targets_url,
    fetch_dumps,
    fetch_targets,
    list_dumps,
    list_targets,
    resolve_target_row,
)
from services.email_dump.origin_ips import (
    build_origin_ips_url,
    fetch_origin_ips,
    import_origin_ips,
    layer_name_for_email,
)
from utils.config import settings
from utils.constants import (
    EMAIL_DUMP_INVALID_RESPONSE,
    EMAIL_DUMP_MODULE_SLUG,
    EMAIL_DUMP_NOT_CONFIGURED,
    EMAIL_DUMP_NOT_FOUND,
    EMAIL_DUMP_RATE_LIMITED,
    EMAIL_DUMP_TIMEOUT,
    EMAIL_DUMP_UNAUTHORIZED,
    EMAIL_DUMP_UNAVAILABLE,
    STATUS_NOT_FOUND,
    STATUS_SERVICE_UNAVAILABLE,
    STATUS_UNAUTHORIZED,
)
from utils.exceptions import (
    AppException,
    GatewayTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)


SAMPLE_PAYLOAD = {
    "success": True,
    "message": "string",
    "data": [
        {
            "email_id": 101,
            "risk_level": "safe",
            "is_suspicious": False,
            "ips": [
                {
                    "ip": "8.8.8.8",
                    "ip_type": "origin",
                    "count": 2,
                    "email_address": "person@example.com",
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "country": "India",
                    "isp": "Example ISP",
                    "first_seen": "2026-01-01T00:00:00Z",
                    "last_seen": "2026-01-02T00:00:00Z",
                }
            ],
        }
    ],
    "meta": {"additionalProp1": {}},
}


# ===================================================
# TEST DOUBLES
# ===================================================

class FakeResponse:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self._payload = payload
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeAsyncClient:
    """Records the outbound call and replays a canned response/error."""

    calls: list[dict] = []
    response: FakeResponse | None = None
    error: Exception | None = None

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, params=None, headers=None):
        type(self).calls.append(
            {"url": url, "params": params, "headers": headers}
        )
        if type(self).error is not None:
            raise type(self).error
        return type(self).response


def _install_fake_client(monkeypatch, response=None, error=None):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = response
    FakeAsyncClient.error = error
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


class FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)

    def __iter__(self):
        return iter(self._values)


class FakeDB:
    """Minimal session double covering every session call the import makes.

    `existing_layer_ids` is consumed one entry per layer lookup, so a
    queued `None` means "no layer found" and a queued id means
    "reuse this layer". `existing_ip_sets` is consumed one entry per
    duplicate-feature lookup.

    Rows added during the import (emails, targets, dumps) are captured in
    `added` so tests can assert on the normalised writes.
    """

    def __init__(self, existing_layer_ids=(), existing_ip_sets=()):
        self._layer_ids = list(existing_layer_ids)
        self._ip_sets = list(existing_ip_sets)
        self.added = []
        self.existing_rows = []

    @staticmethod
    def _entity(stmt):
        """The model class a select() targets, or None if undeterminable."""
        try:
            return stmt.column_descriptions[0]["entity"]
        except (AttributeError, IndexError, KeyError, TypeError):
            return None

    def scalar(self, _stmt):
        entity = self._entity(_stmt)
        if entity is not None and entity is not Layer:
            # An emails / email_targets / email_dumps lookup. These are
            # independent of the queued layer-id lookups, so they are fed
            # from their own list and default to "not found".
            for index, row in enumerate(self.existing_rows):
                if isinstance(row, entity):
                    return self.existing_rows.pop(index)
            return None
        return self._layer_ids.pop(0) if self._layer_ids else None

    def scalars(self, stmt):
        entity = self._entity(stmt)
        if entity in (EmailTarget, EmailDump):
            # A normalised-table listing, which reads the stored rows
            # rather than the queued feature IP sets.
            return FakeScalarResult(
                [row for row in self.existing_rows if isinstance(row, entity)]
            )
        return FakeScalarResult(self._ip_sets.pop(0) if self._ip_sets else [])

    def add(self, row):
        # Rows are keyed by the provider's own identifiers now, so there
        # is no surrogate key for a real session to populate on flush.
        self.added.append(row)

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


def _patch_persistence(monkeypatch, existing_layers=None):
    """Stub the shared GIS layer/feature services and capture writes."""
    state = {"layers": [], "features": [], "existing": dict(existing_layers or {})}

    async def fake_create_layer(payload, db):
        state["layers"].append(payload)
        return {"success": True, "layer_id": len(state["layers"]), "message": "ok"}

    def _layer_dict(layer_id, payload):
        return {
            "id": layer_id,
            "case_id": payload["case_id"],
            "name": payload["name"],
            "layer_type": payload["layer_type"],
            "module_slug": payload["module_slug"],
            "visible": payload["visible"],
            "created_at": None,
        }

    async def fake_get_layer(layer_id, db):
        if layer_id <= len(state["layers"]):
            return _layer_dict(layer_id, state["layers"][layer_id - 1])
        return state["existing"][layer_id]

    def fake_create_features_batch(features, case_id, layer_id, db, created_by=None, module_slug=None):
        state["features"].append(
            {
                "features": features,
                "case_id": case_id,
                "layer_id": layer_id,
                "created_by": created_by,
                "module_slug": module_slug,
            }
        )
        return [
            {
                "id": index + 1,
                "feature_number": index + 1,
                "case_id": case_id,
                "layer_id": layer_id,
                "module_slug": module_slug,
                "name": feature["name"],
                "geometry": feature["geometry"],
                "properties": feature["properties"],
            }
            for index, feature in enumerate(features)
        ]

    monkeypatch.setattr(origin_ips, "create_layer", fake_create_layer)
    monkeypatch.setattr(origin_ips, "get_layer", fake_get_layer)
    monkeypatch.setattr(origin_ips, "create_features_batch", fake_create_features_batch)
    return state


async def _stub_fetch(monkeypatch, records):
    async def fake_fetch(case_id, query, access_token):
        return records

    monkeypatch.setattr(origin_ips, "fetch_origin_ips", fake_fetch)


# ===================================================
# URL CONSTRUCTION
# ===================================================

def test_origin_ips_url_is_built_from_configured_base_url(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")

    assert (
        build_origin_ips_url(123)
        == "http://192.168.6.63:8002/api/emails/single/origin-ips/123"
    )


def test_origin_ips_url_tolerates_trailing_slash(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002/")

    assert (
        build_origin_ips_url(123)
        == "http://192.168.6.63:8002/api/emails/single/origin-ips/123"
    )


def test_origin_ips_url_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "")

    with pytest.raises(AppException) as exc:
        build_origin_ips_url(123)

    assert exc.value.status_code == STATUS_SERVICE_UNAVAILABLE
    assert exc.value.detail == EMAIL_DUMP_NOT_CONFIGURED


def test_layer_name_is_deterministic():
    assert layer_name_for_email(101) == "Email 101"


# ===================================================
# UPSTREAM CALL
# ===================================================

@pytest.mark.asyncio
async def test_fetch_origin_ips_forwards_bearer_token_and_provided_params(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    client = _install_fake_client(monkeypatch, response=FakeResponse(payload=SAMPLE_PAYLOAD))

    records = await fetch_origin_ips(
        123,
        EmailDumpOriginIpQuery(risk_level="high", country="India"),
        "current-token",
    )

    call = client.calls[0]
    assert call["url"] == "http://192.168.6.63:8002/api/emails/single/origin-ips/123"
    assert call["headers"] == {"Authorization": "Bearer current-token"}
    assert call["params"] == {"risk_level": "high", "country": "India"}
    assert len(records) == 1
    assert records[0].email_id == 101
    assert records[0].ips[0].ip == "8.8.8.8"
    assert records[0].ips[0].latitude == 18.5204
    assert records[0].ips[0].longitude == 73.8567


@pytest.mark.asyncio
async def test_fetch_origin_ips_omits_absent_params(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    client = _install_fake_client(monkeypatch, response=FakeResponse(payload=SAMPLE_PAYLOAD))

    await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert client.calls[0]["params"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,expected_status,expected_detail",
    [
        (401, STATUS_UNAUTHORIZED, EMAIL_DUMP_UNAUTHORIZED),
        (403, STATUS_UNAUTHORIZED, EMAIL_DUMP_UNAUTHORIZED),
        (404, STATUS_NOT_FOUND, EMAIL_DUMP_NOT_FOUND),
        (429, STATUS_SERVICE_UNAVAILABLE, EMAIL_DUMP_RATE_LIMITED),
        (500, STATUS_SERVICE_UNAVAILABLE, EMAIL_DUMP_UNAVAILABLE),
        (503, STATUS_SERVICE_UNAVAILABLE, EMAIL_DUMP_UNAVAILABLE),
    ],
)
async def test_fetch_origin_ips_maps_upstream_status(
    monkeypatch, status_code, expected_status, expected_detail
):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(monkeypatch, response=FakeResponse(status_code=status_code))

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.status_code == expected_status
    assert exc.value.detail == expected_detail


@pytest.mark.asyncio
async def test_fetch_origin_ips_maps_timeout_to_gateway_timeout(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(monkeypatch, error=httpx.TimeoutException("slow"))

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.status_code == 504
    assert exc.value.detail == EMAIL_DUMP_TIMEOUT


@pytest.mark.asyncio
async def test_fetch_origin_ips_maps_connection_failure_to_service_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(monkeypatch, error=httpx.ConnectError("refused"))

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.status_code == STATUS_SERVICE_UNAVAILABLE
    assert exc.value.detail == EMAIL_DUMP_UNAVAILABLE


@pytest.mark.asyncio
async def test_fetch_origin_ips_rejects_malformed_json(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(monkeypatch, response=FakeResponse(invalid_json=True))

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.status_code == STATUS_SERVICE_UNAVAILABLE
    assert exc.value.detail == EMAIL_DUMP_INVALID_RESPONSE


@pytest.mark.asyncio
async def test_fetch_origin_ips_rejects_missing_data_array(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "message": "string"}),
    )

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.status_code == STATUS_SERVICE_UNAVAILABLE
    assert exc.value.detail == EMAIL_DUMP_INVALID_RESPONSE


@pytest.mark.asyncio
async def test_fetch_origin_ips_rejects_unexpected_record_shape(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [{"risk_level": "safe"}]}),
    )

    with pytest.raises(AppException) as exc:
        await fetch_origin_ips(123, EmailDumpOriginIpQuery(), "current-token")

    assert exc.value.detail == EMAIL_DUMP_INVALID_RESPONSE


# ===================================================
# LAYER / FEATURE MAPPING
# ===================================================

@pytest.mark.asyncio
async def test_import_origin_ips_maps_email_to_layer_and_ip_to_feature(monkeypatch):
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    records = EmailDumpOriginIpResponse.model_validate(SAMPLE_PAYLOAD).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    response = await import_origin_ips(
        123, EmailDumpOriginIpQuery(), "current-token", FakeDB(), created_by=7
    )

    assert response.success is True
    assert response.case_id == 123
    assert response.module_slug == EMAIL_DUMP_MODULE_SLUG
    assert (response.layers_created, response.layers_reused) == (1, 0)
    assert (response.features_created, response.features_reused) == (1, 0)
    assert response.skipped_coordinates == 0

    layer = state["layers"][0]
    assert layer == {
        "case_id": 123,
        "name": "Email 101",
        "layer_type": "email",
        "module_slug": EMAIL_DUMP_MODULE_SLUG,
        "visible": True,
    }
    assert response.layers[0].id == 1
    assert response.layers[0].module_slug == EMAIL_DUMP_MODULE_SLUG

    batch = state["features"][0]
    assert batch["module_slug"] == EMAIL_DUMP_MODULE_SLUG
    assert batch["case_id"] == 123
    assert batch["layer_id"] == 1
    assert batch["created_by"] == 7

    feature = batch["features"][0]
    assert feature["name"] == "IP 8.8.8.8"
    assert feature["geometry_type"] == "Point"
    assert feature["geometry"] == {"type": "Point", "coordinates": [73.8567, 18.5204]}
    assert feature["properties"] == {
        "email_id": 101,
        "ip": "8.8.8.8",
        "ip_type": "origin",
        "count": 2,
        "email_address": "person@example.com",
        "risk_level": "safe",
        "is_suspicious": False,
        "country": "India",
        "isp": "Example ISP",
        "first_seen": "2026-01-01T00:00:00+00:00",
        "last_seen": "2026-01-02T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_import_origin_ips_creates_one_point_per_valid_ip(monkeypatch):
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    payload = {
        "success": True,
        "data": [
            {
                "email_id": 101,
                "risk_level": "safe",
                "is_suspicious": False,
                "ips": [
                    {"ip": "8.8.8.8", "ip_type": "origin", "count": 2,
                     "latitude": 18.5204, "longitude": 73.8567},
                    {"ip": "1.1.1.1", "ip_type": "origin", "count": 1,
                     "latitude": -33.8688, "longitude": 151.2093},
                    {"ip": "9.9.9.9", "ip_type": "origin", "count": 1,
                     "latitude": 0.0, "longitude": 0.0},
                ],
            }
        ],
    }
    records = EmailDumpOriginIpResponse.model_validate(payload).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    response = await import_origin_ips(
        123, EmailDumpOriginIpQuery(), "current-token", FakeDB()
    )

    assert response.features_created == 3
    assert response.skipped_coordinates == 0
    coordinates = [
        feature["geometry"]["coordinates"] for feature in state["features"][0]["features"]
    ]
    assert coordinates == [[73.8567, 18.5204], [151.2093, -33.8688], [0.0, 0.0]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin_ip",
    [
        {"ip": "8.8.8.8", "ip_type": "origin"},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": 18.5204},
        {"ip": "8.8.8.8", "ip_type": "origin", "longitude": 73.8567},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": 91.0, "longitude": 73.8567},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": -90.5, "longitude": 73.8567},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": 18.5204, "longitude": 180.5},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": 18.5204, "longitude": -180.5},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": "not-a-number", "longitude": 73.8567},
        {"ip": "8.8.8.8", "ip_type": "origin", "latitude": None, "longitude": None},
    ],
)
async def test_import_origin_ips_skips_missing_or_invalid_coordinates(
    monkeypatch, origin_ip
):
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    records = EmailDumpOriginIpResponse.model_validate(
        {"success": True, "data": [{"email_id": 101, "ips": [origin_ip]}]}
    ).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    response = await import_origin_ips(
        123, EmailDumpOriginIpQuery(), "current-token", FakeDB()
    )

    assert response.skipped_coordinates == 1
    assert response.features_created == 0
    assert state["features"] == []
    # The layer is still created so the email is visible in the case.
    assert response.layers_created == 1


@pytest.mark.asyncio
async def test_import_origin_ips_reuses_layers_and_features(monkeypatch):
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    records = EmailDumpOriginIpResponse.model_validate(SAMPLE_PAYLOAD).data
    await _stub_fetch(monkeypatch, records)

    first_state = _patch_persistence(monkeypatch)
    await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", FakeDB())
    assert first_state["layers"] and first_state["features"]

    # Second import: the layer id and the stored IP already exist.
    second_state = _patch_persistence(
        monkeypatch,
        existing_layers={
            25: {
                "id": 25,
                "case_id": 123,
                "name": "Email 101",
                "layer_type": "email",
                "module_slug": EMAIL_DUMP_MODULE_SLUG,
                "visible": True,
                "created_at": None,
            }
        },
    )
    response = await import_origin_ips(
        123,
        EmailDumpOriginIpQuery(),
        "token",
        FakeDB(existing_layer_ids=[25], existing_ip_sets=[["8.8.8.8"]]),
    )

    assert second_state["layers"] == []
    assert second_state["features"] == []
    assert (response.layers_created, response.layers_reused) == (0, 1)
    assert (response.features_created, response.features_reused) == (0, 1)
    assert response.layers[0].id == 25
    assert response.layers[0].name == "Email 101"
    assert response.layers[0].module_slug == EMAIL_DUMP_MODULE_SLUG


@pytest.mark.asyncio
async def test_import_origin_ips_is_case_scoped(monkeypatch):
    """An identical email_id in a second case gets its own layer."""
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    records = EmailDumpOriginIpResponse.model_validate(SAMPLE_PAYLOAD).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    response = await import_origin_ips(456, EmailDumpOriginIpQuery(), "token", FakeDB())

    assert state["layers"][0]["case_id"] == 456
    assert state["features"][0]["case_id"] == 456
    assert response.case_id == 456


@pytest.mark.asyncio
async def test_import_origin_ips_creates_one_layer_per_email(monkeypatch):
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    payload = {
        "success": True,
        "data": [
            {"email_id": 101, "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}]},
            {"email_id": 102, "risk_level": "high", "is_suspicious": True,
             "ips": [{"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093}]},
        ],
    }
    records = EmailDumpOriginIpResponse.model_validate(payload).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    response = await import_origin_ips(
        123, EmailDumpOriginIpQuery(), "token", FakeDB()
    )

    assert [layer["name"] for layer in state["layers"]] == ["Email 101", "Email 102"]
    assert {layer.id for layer in response.layers} == {1, 2}
    assert [batch["layer_id"] for batch in state["features"]] == [1, 2]
    assert state["features"][1]["features"][0]["properties"]["is_suspicious"] is True
    assert response.features_created == 2


@pytest.mark.asyncio
async def test_import_origin_ips_creates_one_layer_per_duplicate_email_id(monkeypatch):
    """Repeated email_ids in one payload collapse onto the same layer."""
    from schemas.email_dump_schema import EmailDumpOriginIpResponse

    payload = {
        "success": True,
        "data": [
            {"email_id": 101, "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}]},
            {"email_id": 101, "ips": [{"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093}]},
        ],
    }
    records = EmailDumpOriginIpResponse.model_validate(payload).data
    await _stub_fetch(monkeypatch, records)
    state = _patch_persistence(monkeypatch)

    # The first lookup misses; the second finds the layer just created.
    db = FakeDB(existing_layer_ids=[None, 1])
    response = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert len(state["layers"]) == 1
    assert (response.layers_created, response.layers_reused) == (1, 1)
    assert response.features_created == 2


# ===================================================
# ROUTE
# ===================================================

def test_email_dump_route_is_registered():
    paths = {
        route.path: route.methods
        for route in app.routes
        if getattr(route, "path", "").endswith("/email-dump/origin-ips")
    }

    assert paths == {"/cases/{case_id}/email-dump/origin-ips": {"GET"}}


def test_email_dump_route_requires_authentication():
    client = TestClient(app)

    assert client.get("/cases/123/email-dump/origin-ips").status_code == 401


def test_email_dump_route_forwards_filters_and_returns_gis_summary(monkeypatch):
    """Frontend -> GIS -> Email Dump: filters reach the provider unchanged."""
    from utils.dependencies import get_current_case_context

    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")
    client_double = _install_fake_client(monkeypatch, response=FakeResponse(payload=SAMPLE_PAYLOAD))
    state = _patch_persistence(monkeypatch)

    async def fake_case_context():
        return {"user_id": 7, "email": "analyst@example.com", "role": "investigator", "case_id": 123}

    app.dependency_overrides[get_current_case_context] = fake_case_context
    app.dependency_overrides[get_db] = lambda: FakeDB()

    try:
        client = TestClient(app)
        response = client.get(
            "/cases/123/email-dump/origin-ips",
            params={"risk_level": "high", "country": "India", "is_suspicious": "true"},
            headers={"Authorization": "Bearer current-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "case_id": 123,
        "module_slug": EMAIL_DUMP_MODULE_SLUG,
        "layers_created": 1,
        "layers_reused": 0,
        "features_created": 1,
        "features_reused": 0,
        "skipped_coordinates": 0,
        "emails_created": 1,
        "emails_updated": 0,
        "targets_created": 0,
        "targets_updated": 0,
        "dumps_created": 0,
        "dumps_updated": 0,
        "layers": [
            {
                "id": 1,
                "case_id": 123,
                "name": "Email 101",
                "layer_type": "email",
                "module_slug": EMAIL_DUMP_MODULE_SLUG,
                "visible": True,
            }
        ],
    }

    call = client_double.calls[0]
    assert call["url"] == "http://192.168.6.63:8002/api/emails/single/origin-ips/123"
    assert call["headers"] == {"Authorization": "Bearer current-token"}
    assert call["params"] == {
        "risk_level": "high",
        "country": "India",
        "is_suspicious": True,
    }
    assert state["features"][0]["created_by"] == 7



# ===================================================
# NORMALISED TABLES: emails / email_targets / email_dumps
# ===================================================


@pytest.mark.asyncio
async def test_import_persists_one_email_row_per_ip(monkeypatch):
    """Every property that used to live only in features.properties is
    now a real column in `emails`, one row per (email_id, ip)."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload= {"success": True, "data": [{
            "email_id": 101,
            "risk_level": "high",
            "is_suspicious": True,
            "ips": [
                {"ip": "8.8.8.8", "ip_type": "origin", "count": 4,
                 "email_address": "a@example.com", "latitude": 18.5204,
                 "longitude": 73.8567, "country": "India", "isp": "Google",
                 "first_seen": "2026-01-01T00:00:00Z", "last_seen": "2026-01-02T00:00:00Z"},
                {"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093},
            ],
        }]}),
    )
    state = _patch_persistence(monkeypatch)
    db = FakeDB()

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    emails = [row for row in db.added if isinstance(row, EmailRecord)]
    assert len(emails) == 2
    assert result.emails_created == 2

    first = emails[0]
    assert first.case_id == 123
    assert first.email_id == 101
    assert first.ip == "8.8.8.8"
    assert first.email_address == "a@example.com"
    assert first.ip_type == "origin"
    assert first.count == 4
    assert first.risk_level == "high"
    assert first.is_suspicious is True
    assert first.country == "India"
    assert first.isp == "Google"
    assert first.first_seen is not None
    assert first.last_seen is not None

    # The IP feature layer is still created exactly as before.
    assert state["features"][0]["features"][0]["properties"]["ip"] == "8.8.8.8"


@pytest.mark.asyncio
async def test_import_persists_targets_and_dumps(monkeypatch):
    """target_id from the upstream response lands in email_targets, and
    its dumps land in email_dumps keyed to the target."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload= {"success": True, "data": [{
            "email_id": 101,
            "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}],
            "targets": [
                {
                    "target_id": "TGT-9",
                    "target_name": "Acme Corp",
                    "dumps": [
                        {"dump_id": "D1", "name": "March dump"},
                        {"dump_id": "D2", "name": "April dump"},
                    ],
                }
            ],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    targets = [row for row in db.added if isinstance(row, EmailTarget)]
    dumps = [row for row in db.added if isinstance(row, EmailDump)]
    assert len(targets) == 1
    assert len(dumps) == 2

    target = targets[0]
    assert target.case_id == 123
    assert target.target_id == "TGT-9"
    assert target.target_name == "Acme Corp"
    # email_id records the provider's email, not a row of `emails`.
    assert target.email_id == 101

    assert result.targets_created == 1
    assert result.dumps_created == 2
    assert {d.dump_id for d in dumps} == {"D1", "D2"}
    # The dumps reference the target by the provider's own identifier.
    assert all(d.target_id == "TGT-9" for d in dumps)
    assert {d.name for d in dumps} == {"March dump", "April dump"}


@pytest.mark.asyncio
async def test_import_attaches_targets_to_one_email_row_only(monkeypatch):
    """A target belongs to an email, not to each of its IP rows, so a
    multi-IP email still gets exactly one target row."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload= {"success": True, "data": [{
            "email_id": 101,
            "ips": [
                {"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567},
                {"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093},
            ],
            "targets": [{"target_id": "TGT-9", "dumps": [{"dump_id": "D1"}]}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert result.emails_created == 2
    assert result.targets_created == 1
    assert len([r for r in db.added if isinstance(r, EmailTarget)]) == 1


@pytest.mark.asyncio
async def test_import_updates_existing_rows_instead_of_duplicating(monkeypatch):
    """Re-importing the same payload updates the existing rows."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload= {"success": True, "data": [{
            "email_id": 101,
            "risk_level": "low",
            "ips": [                {"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}],
            "targets": [{"target_id": "TGT-9", "target_name": "New", "dumps": [{"dump_id": "D1"}]}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()

    existing_email = EmailRecord(case_id=123, email_id=101, ip="8.8.8.8", risk_level="high")
    existing_target = EmailTarget(case_id=123, email_id=101, target_id="TGT-9", target_name="Old")
    existing_dump = EmailDump(case_id=123, target_id="TGT-9", dump_id="D1", name="Old dump")
    db.existing_rows = [existing_email, existing_target, existing_dump]

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert result.emails_created == 0
    assert result.emails_updated == 1
    assert result.targets_updated == 1
    assert result.dumps_updated == 1
    assert existing_email.risk_level == "low"
    # No new rows were inserted: the existing ones were updated in place.
    assert db.added == []


@pytest.mark.asyncio
async def test_import_overwrites_stale_target_and_dump_names(monkeypatch):
    """A re-import refreshes the cached names rather than keeping the
    stale ones."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [{
            "email_id": 101,
            "ips": [
                {"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567},
            ],
            "targets": [{"target_id": "TGT-9", "target_name": "New",
                         "dumps": [{"dump_id": "D1", "name": "New dump"}]}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()

    existing_email = EmailRecord(case_id=123, email_id=101, ip="8.8.8.8")
    existing_target = EmailTarget(case_id=123, email_id=101, target_id="TGT-9", target_name="Old")
    existing_dump = EmailDump(case_id=123, target_id="TGT-9", dump_id="D1", name="Old dump")
    db.existing_rows = [existing_email, existing_target, existing_dump]

    await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert existing_target.target_name == "New"
    assert existing_dump.name == "New dump"


@pytest.mark.asyncio
async def test_import_works_without_targets_in_payload(monkeypatch):
    """A payload with no `targets` key still imports, matching the
    current upstream response."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload= {"success": True, "data": [{
            "email_id": 101,
            "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert result.success is True
    assert result.emails_created == 1
    assert result.targets_created == 0
    assert result.dumps_created == 0


# ===================================================
# DUMPS LISTING (target dropdown)
# ===================================================

def _target_row(case_id=123, target_id="TGT-42", email_id=7):
    return EmailTarget(case_id=case_id, email_id=email_id, target_id=target_id, target_name="Campaign")


def _dumps_payload(*items):
    return {"data": list(items)}


# Distinguishes "argument omitted" from an explicit None, since None means
# "this target was never imported".
_UNSET = object()


class DumpsDB(FakeDB):
    """FakeDB with a stable target row, for the dumps route.

    `resolve_target_row` uses scalar() and `_cache_dumps` uses scalars()
    + add() + commit(), so the inherited double already covers the calls;
    this subclass only fixes a single target that is always found.
    """

    def __init__(self, target=_UNSET):
        # Omitting `target` gives a found target row; passing None
        # explicitly models "this target was never imported".
        super().__init__()
        self.target = _target_row() if target is _UNSET else target

    def scalar(self, stmt):
        if self._entity(stmt) is EmailTarget:
            return self.target
        return None

    def scalars(self, stmt):
        # _cache_dumps reads existing dumps for the target; seeded per test.
        if self._entity(stmt) is EmailDump:
            return FakeScalarResult(self.existing_rows)
        return FakeScalarResult([])


# --- URL construction -------------------------------------------------

def test_dumps_url_uses_configured_base_url(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")

    assert build_dumps_url(123) == "http://192.168.6.63:8002/api/dumps/single/123"


def test_dumps_url_tolerates_trailing_slash(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002/")

    assert build_dumps_url(123) == "http://192.168.6.63:8002/api/dumps/single/123"


def test_dumps_url_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", None)

    with pytest.raises(ServiceUnavailableError):
        build_dumps_url(123)


# --- upstream fetch ---------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_dumps_forwards_bearer_token_and_target_id(monkeypatch):
    fake = _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload=_dumps_payload({"dump_id": "D1", "name": "One"})),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "TGT-42", "token")

    call = fake.calls[0]
    assert call["url"] == "http://provider:8002/api/dumps/single/123"
    assert call["params"] == {"target_id": "TGT-42"}
    assert call["headers"] == {"Authorization": "Bearer token"}
    assert [(d.dump_id, d.name) for d in dumps] == [("D1", "One")]


@pytest.mark.asyncio
async def test_fetch_dumps_accepts_bare_list(monkeypatch):
    """A payload that is just a list is still readable."""
    _install_fake_client(
        monkeypatch, response=FakeResponse(payload=[{"dump_id": "D1", "name": "One"}])
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "TGT-42", "token")

    assert [d.dump_id for d in dumps] == ["D1"]


@pytest.mark.asyncio
async def test_fetch_dumps_drops_entries_without_an_identifier(monkeypatch):
    """`dump_id` is the only identifier upstream; an entry without one
    cannot be stored and is dropped rather than persisted."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(
            payload=_dumps_payload(
                {"dump_id": "D1", "name": "One"},
                {"total_emails": 5},
                {"dump_id": "  "},
            )
        ),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "TGT-42", "token")

    assert [(d.dump_id, d.name) for d in dumps] == [("D1", "One")]


@pytest.mark.asyncio
async def test_fetch_dumps_rejects_unrecognisable_payload(monkeypatch):
    """A payload with no list anywhere is an upstream fault, not an
    empty result."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload={"unexpected": True}))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(ServiceUnavailableError):
        await fetch_dumps(123, "TGT-42", "token")


@pytest.mark.asyncio
async def test_fetch_dumps_rejects_malformed_json(monkeypatch):
    _install_fake_client(
        monkeypatch, response=FakeResponse(invalid_json=True)
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(ServiceUnavailableError):
        await fetch_dumps(123, "TGT-42", "token")


@pytest.mark.asyncio
async def test_fetch_dumps_maps_upstream_401_without_leaking_body(monkeypatch):
    _install_fake_client(monkeypatch, response=FakeResponse(status_code=401, payload={"error": "nope"}))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(UnauthorizedError):
        await fetch_dumps(123, "TGT-42", "token")


@pytest.mark.asyncio
async def test_fetch_dumps_maps_upstream_429(monkeypatch):
    _install_fake_client(monkeypatch, response=FakeResponse(status_code=429, payload={}))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(ServiceUnavailableError):
        await fetch_dumps(123, "TGT-42", "token")


@pytest.mark.asyncio
async def test_fetch_dumps_maps_timeout(monkeypatch):
    _install_fake_client(monkeypatch, error=httpx.TimeoutException("slow"))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(GatewayTimeoutError):
        await fetch_dumps(123, "TGT-42", "token")


# --- target resolution ------------------------------------------------

def test_resolve_target_row_returns_none_for_unimported_target():
    """No email_targets row means there is nothing to cache against, but
    it is not an error: the provider may know a target the import never
    wrote."""
    db = DumpsDB(target=None)

    assert resolve_target_row(123, "TGT-99", db) is None


def test_resolve_target_row_returns_the_imported_row():
    db = DumpsDB()

    assert resolve_target_row(123, "TGT-42", db) is db.target


# --- end to end -------------------------------------------------------

@pytest.mark.asyncio
async def test_list_dumps_caches_new_dumps_and_returns_them(monkeypatch):
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload=_dumps_payload(
            {"dump_id": "D1", "name": "One"}, {"dump_id": "D2", "name": "Two"}
        )),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()

    result = await list_dumps(123, "TGT-42", "token", db)

    assert result.success is True
    assert result.case_id == 123
    assert result.target_id == "TGT-42"
    assert [(d.dump_id, d.name) for d in result.dumps] == [("D1", "One"), ("D2", "Two")]
    assert result.dumps_created == 2
    assert result.dumps_updated == 0
    assert result.from_cache is False
    # Rows reference the target by the provider's own identifier.
    assert [(row.target_id, row.dump_id) for row in db.added] == [
        ("TGT-42", "D1"),
        ("TGT-42", "D2"),
    ]
    assert all(row.case_id == 123 for row in db.added)


@pytest.mark.asyncio
async def test_list_dumps_refreshes_name_instead_of_duplicating(monkeypatch):
    _install_fake_client(
        monkeypatch, response=FakeResponse(payload=_dumps_payload({"dump_id": "D1", "name": "New"}))
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    existing_dump = EmailDump(case_id=123, target_id="TGT-42", dump_id="D1", name="Old")
    db = DumpsDB()
    db.existing_rows = [existing_dump]

    result = await list_dumps(123, "TGT-42", "token", db)

    assert existing_dump.name == "New"
    assert result.dumps_created == 0
    assert result.dumps_updated == 1
    assert db.added == []


@pytest.mark.asyncio
async def test_list_dumps_keeps_unchanged_names_out_of_the_update_count(monkeypatch):
    """A dump whose name already matches is not counted as updated, so
    the counters describe real changes."""
    _install_fake_client(
        monkeypatch, response=FakeResponse(payload=_dumps_payload({"dump_id": "D1", "name": "Same"}))
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.existing_rows = [EmailDump(case_id=123, target_id="TGT-42", dump_id="D1", name="Same")]

    result = await list_dumps(123, "TGT-42", "token", db)

    assert result.dumps_updated == 0
    assert result.dumps == [EmailDumpRef(dump_id="D1", name="Same")]


@pytest.mark.asyncio
async def test_list_dumps_returns_empty_list_when_target_has_no_dumps(monkeypatch):
    """No dumps is a valid answer, not an error."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=_dumps_payload()))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    result = await list_dumps(123, "TGT-42", "token", DumpsDB())

    assert result.success is True
    assert result.dumps == []
    assert result.from_cache is False


@pytest.mark.asyncio
async def test_list_dumps_falls_back_to_cache_when_upstream_returns_nothing(monkeypatch):
    """An empty upstream list must not wipe the dropdown, so previously
    cached rows are served instead."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=_dumps_payload()))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.existing_rows = [EmailDump(case_id=123, target_id="TGT-42", dump_id="D1", name="Cached")]

    result = await list_dumps(123, "TGT-42", "token", db)

    assert result.from_cache is True
    assert [(d.dump_id, d.name) for d in result.dumps] == [("D1", "Cached")]


@pytest.mark.asyncio
async def test_list_dumps_calls_upstream_for_an_unimported_target(monkeypatch):
    """A target the provider lists but the import never wrote is still
    worth answering, so the provider is called and nothing is cached."""
    fake = _install_fake_client(
        monkeypatch, response=FakeResponse(payload=_dumps_payload({"dump_id": "D1"}))
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB(target=None)

    result = await list_dumps(123, "TGT-99", "token", db)

    assert [d.dump_id for d in result.dumps] == ["D1"]
    assert result.dumps_created == 0
    assert db.added == []
    assert len(fake.calls) == 1


# --- targets listing (real shape from the provider's openapi.json) -----

TARGETS_PAYLOAD = {
    "success": True,
    "message": None,
    "data": [
        {
            "target_id": 42,
            "target_email": "bad@evil.example",
            "dump_count": 2,
            "dump_ids": ["DMP-1", "DMP-2"],
            "dump_statuses": {"DMP-1": "complete", "DMP-2": "processing"},
            "report_id": 7,
        }
    ],
    "meta": None,
}

DUMPS_PAYLOAD = {
    "success": True,
    "message": None,
    "data": [
        {
            "dump_id": "DMP-1",
            "total_emails": 1200,
            "malicious_count": 34,
            "unique_senders": 210,
            "unique_recipients": 88,
            "start_date": "2026-09-01T00:00:00Z",
            "end_date": "2026-09-20T00:00:00Z",
            "created_at": "2026-09-21T10:30:00Z",
        }
    ],
    "meta": None,
}


def test_targets_url_matches_provider_documented_path(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://192.168.6.63:8002")

    assert build_targets_url(123) == "http://192.168.6.63:8002/api/cases/123/targets"


def test_targets_url_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", None)

    with pytest.raises(ServiceUnavailableError):
        build_targets_url(123)


@pytest.mark.asyncio
async def test_fetch_targets_forwards_token_without_target_filter(monkeypatch):
    """The targets route takes no target_id: it lists a whole case."""
    fake = _install_fake_client(monkeypatch, response=FakeResponse(payload=TARGETS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    targets = await fetch_targets(123, "token")

    call = fake.calls[0]
    assert call["url"] == "http://provider:8002/api/cases/123/targets"
    assert call["params"] is None
    assert call["headers"] == {"Authorization": "Bearer token"}
    assert len(targets) == 1
    assert targets[0].target_id == 42
    assert targets[0].target_email == "bad@evil.example"
    assert targets[0].dump_ids == ["DMP-1", "DMP-2"]
    assert targets[0].dump_statuses == {"DMP-1": "complete", "DMP-2": "processing"}
    assert targets[0].report_id == 7


@pytest.mark.asyncio
async def test_fetch_targets_skips_entries_missing_identity(monkeypatch):
    """A target with no id or email is unusable and is dropped, with the
    rest of the list still returned."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"data": [
            {"target_id": 42, "target_email": "a@b.com"},
            {"target_email": "no-id@x.com"},
            {"target_id": 43},
        ]}),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    targets = await fetch_targets(123, "token")

    assert [t.target_id for t in targets] == [42]


@pytest.mark.asyncio
async def test_fetch_targets_derives_dump_count_when_absent(monkeypatch):
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"data": [
            {"target_id": 42, "target_email": "a@b.com", "dump_ids": ["D1", "D2", "D3"]},
        ]}),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    targets = await fetch_targets(123, "token")

    assert targets[0].dump_count == 3


@pytest.mark.asyncio
async def test_fetch_targets_rejects_payload_without_data(monkeypatch):
    _install_fake_client(monkeypatch, response=FakeResponse(payload={"success": True}))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    with pytest.raises(ServiceUnavailableError):
        await fetch_targets(123, "token")


@pytest.mark.asyncio
async def test_list_targets_stores_every_fetched_target(monkeypatch):
    """Fetching the targets writes them to email_targets, so a target
    picked from the dropdown is a real row."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=TARGETS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = FakeDB()

    result = await list_targets(123, "token", db)

    assert result.case_id == 123
    assert result.targets_count == 1
    assert result.targets[0].dump_ids == ["DMP-1", "DMP-2"]

    stored = [r for r in db.added if isinstance(r, EmailTarget)]
    assert len(stored) == 1
    assert stored[0].case_id == 123
    # The listing documents target_id as an integer; the column is text.
    assert stored[0].target_id == str(result.targets[0].target_id)
    # The listing does not say which email reported the target, so that
    # is left for the import to fill in.
    assert stored[0].email_id is None
    assert stored[0].target_name == result.targets[0].target_email


@pytest.mark.asyncio
async def test_relisting_targets_updates_rather_than_duplicates(monkeypatch):
    """Listing the same targets twice keeps one row each."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=TARGETS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = FakeDB()
    await list_targets(123, "token", db)
    first = [r for r in db.added if isinstance(r, EmailTarget)][0]

    db2 = FakeDB()
    db2.existing_rows = [first]
    await list_targets(123, "token", db2)

    assert db2.added == []


@pytest.mark.asyncio
async def test_listing_targets_does_not_clobber_an_imported_name(monkeypatch):
    """The import's target name is the real one, so a later listing
    leaves it alone instead of replacing it with an address."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=TARGETS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    target_id = str(TARGETS_PAYLOAD["data"][0]["target_id"])
    imported = EmailTarget(
        case_id=123, target_id=target_id, email_id=101, target_name="Acme Corp"
    )
    db = FakeDB()
    db.existing_rows = [imported]

    await list_targets(123, "token", db)

    assert imported.target_name == "Acme Corp"
    assert imported.email_id == 101


# --- dumps parsing against the documented EmailDumpSchema --------------

@pytest.mark.asyncio
async def test_fetch_dumps_reads_all_counters_and_dates(monkeypatch):
    """A dump is counters, not a name: every documented field is read."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "42", "token")

    assert len(dumps) == 1
    dump = dumps[0]
    assert dump.dump_id == "DMP-1"
    assert dump.total_emails == 1200
    assert dump.malicious_count == 34
    assert dump.unique_senders == 210
    assert dump.unique_recipients == 88
    assert dump.start_date.year == 2026 and dump.start_date.month == 9
    assert dump.created_at is not None
    # Upstream sends no name at all.
    assert dump.name is None


@pytest.mark.asyncio
async def test_fetch_dumps_tolerates_malformed_counters(monkeypatch):
    """A bad counter degrades to null instead of failing the listing."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"data": [
            {"dump_id": "DMP-1", "total_emails": "many", "start_date": "not-a-date",
             "malicious_count": None},
        ]}),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "42", "token")

    assert dumps[0].dump_id == "DMP-1"
    assert dumps[0].total_emails is None
    assert dumps[0].start_date is None
    assert dumps[0].malicious_count is None


@pytest.mark.asyncio
async def test_fetch_dumps_normalises_offset_timestamps_to_naive_utc(monkeypatch):
    """The provider sends RFC 3339 with an offset but the columns are
    naive, so a kept offset would make every dump look changed on every
    listing."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"data": [
            {"dump_id": "DMP-1", "created_at": "2026-09-01T12:00:00+05:30"},
        ]}),
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    dumps = await fetch_dumps(123, "42", "token")

    created = dumps[0].created_at
    assert created.tzinfo is None
    assert (created.hour, created.minute) == (6, 30)


@pytest.mark.asyncio
async def test_repeat_listing_of_an_unchanged_dump_reports_no_update(monkeypatch):
    """A dump that has not changed must not be counted as updated: this
    is the case an offset timestamp would break."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.existing_rows = [
        EmailDump(
            case_id=123, target_id="42", dump_id="DMP-1",
            total_emails=1200, malicious_count=34, unique_senders=210,
            unique_recipients=88,
            start_date=datetime(2026, 9, 1, 0, 0), end_date=datetime(2026, 9, 20, 0, 0),
            provider_created_at=datetime(2026, 9, 21, 10, 30),
        )
    ]

    result = await list_dumps(123, "42", "token", db)

    assert result.dumps_created == 0
    assert result.dumps_updated == 0


@pytest.mark.asyncio
async def test_fetch_dumps_accepts_numeric_target_id(monkeypatch):
    """The provider's target_id is an integer; it is forwarded as sent."""
    fake = _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")

    await fetch_dumps(123, "42", "token")

    assert fake.calls[0]["params"] == {"target_id": "42"}


@pytest.mark.asyncio
async def test_list_dumps_matches_numeric_target_id_against_stored_text(monkeypatch):
    """email_targets.target_id is a string column while the provider
    sends an integer, so a numeric id must still resolve."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.target = EmailTarget(case_id=123, email_id=7, target_id="42", target_name="T")

    result = await list_dumps(123, "42", "token", db)

    assert result.dumps_created == 1
    added = db.added[0]
    assert added.dump_id == "DMP-1"
    assert added.total_emails == 1200
    assert added.malicious_count == 34
    assert added.unique_senders == 210
    assert added.unique_recipients == 88
    assert added.provider_created_at is not None


@pytest.mark.asyncio
async def test_list_dumps_still_serves_unimported_targets(monkeypatch):
    """A target the provider knows about but the import never wrote has
    no local row; the dumps are still returned, just uncached."""
    _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB(target=None)

    result = await list_dumps(123, "42", "token", db)

    assert result.success is True
    assert [d.dump_id for d in result.dumps] == ["DMP-1"]
    assert db.added == []


@pytest.mark.asyncio
async def test_list_dumps_counts_a_changed_counter_as_an_update(monkeypatch):
    _install_fake_client(monkeypatch, response=FakeResponse(payload=DUMPS_PAYLOAD))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.existing_rows = [EmailDump(case_id=123, target_id="42", dump_id="DMP-1", total_emails=1)]

    result = await list_dumps(123, "42", "token", db)

    assert result.dumps_created == 0
    assert result.dumps_updated == 1
    assert db.existing_rows[0].total_emails == 1200


@pytest.mark.asyncio
async def test_list_dumps_cache_fallback_includes_counters(monkeypatch):
    _install_fake_client(monkeypatch, response=FakeResponse(payload={"data": []}))
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    db = DumpsDB()
    db.existing_rows = [
        EmailDump(case_id=123, target_id="42", dump_id="DMP-1",
                  total_emails=1200, malicious_count=34)
    ]

    result = await list_dumps(123, "42", "token", db)

    assert result.from_cache is True
    assert result.dumps[0].total_emails == 1200
    assert result.dumps[0].malicious_count == 34


# ===================================================
# NATURAL KEYS AND LAYER LINKING
# ===================================================

def test_no_table_carries_a_surrogate_id():
    """The provider's own identifiers are the keys, so no table has an
    extra `id` column for the backend to keep in step."""
    for model in (EmailRecord, EmailTarget, EmailDump):
        assert "id" not in model.__table__.columns, model.__tablename__
        assert model.__table__.primary_key.columns, model.__tablename__


def test_primary_keys_are_the_provider_identifiers():
    """Each table is keyed on the provider's identifiers within a case."""
    def key_names(model):
        return [c.name for c in model.__table__.primary_key]

    assert key_names(EmailRecord) == ["case_id", "email_id", "ip"]
    assert key_names(EmailTarget) == ["case_id", "target_id"]
    assert key_names(EmailDump) == ["case_id", "dump_id"]


def test_email_target_is_not_a_foreign_key_to_emails():
    """An email has one row per IP, so there is no single emails row for
    a target to point at; email_id is the provider's identifier instead."""
    target_fks = {
        (tuple(fk.constraint.column_keys), fk.target_fullname)
        for fk in EmailTarget.__table__.foreign_keys
    }
    assert not any("emails" in target for _, target in target_fks), target_fks
    assert EmailTarget.email_id.nullable


def test_dump_links_to_its_target_on_both_key_columns():
    """The target link is a real composite constraint, so deleting a
    target still takes its dumps with it."""
    fks = {
        tuple(fk.constraint.column_keys)
        for fk in EmailDump.__table__.foreign_keys
        if fk.target_fullname.startswith("email_targets")
    }
    assert ("case_id", "target_id") in fks, fks


def test_only_emails_links_to_a_layer():
    """`emails` is the one table with a row per point feature, so it is
    the one that belongs to a layer. Targets and dumps hold no geometry
    and were storing the email's layer as a proxy."""
    assert "layer_id" in EmailRecord.__table__.columns
    assert "layer_id" not in EmailTarget.__table__.columns
    assert "layer_id" not in EmailDump.__table__.columns


def test_the_same_ip_may_belong_to_different_emails():
    """A shared IP is two separate rows: uniqueness is per email, not
    per case."""
    key = EmailRecord.__table__.primary_key.columns
    assert "email_id" in [c.name for c in key]


def test_provider_integer_identifiers_are_accepted():
    """The provider documents target_id as an integer while the models
    keep identifiers as text, so the numeric form has to survive
    validation rather than being dropped or rejected."""
    assert EmailTargetRef(target_id=42).target_id == "42"
    assert EmailDumpRef(dump_id=7).dump_id == "7"
    # A float that is not integral is not an identifier.
    with pytest.raises(ValueError):
        EmailTargetRef(target_id=1.5)


@pytest.mark.asyncio
async def test_import_fills_in_a_target_the_listing_already_stored(monkeypatch):
    """A target picked from the dropdown exists with no email_id, because
    the listing does not say which email reported it. The import does, so
    it enriches that row instead of creating a second one."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [{
            "email_id": 101,
            "ips": [
                {"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567},
                {"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093},
            ],
            "targets": [{"target_id": "TGT-9", "target_name": "Acme Corp",
                         "dumps": [{"dump_id": "D1"}]}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()
    from_listing = EmailTarget(
        case_id=123, target_id="TGT-9", target_name="victim@acme.com"
    )
    db.existing_rows = [from_listing]

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    # The existing row was updated in place, not duplicated.
    assert result.targets_updated == 1
    assert result.targets_created == 0
    assert from_listing.email_id == 101
    # The payload's name is the real one, so it replaces the listing's
    # fallback address.
    assert from_listing.target_name == "Acme Corp"
    assert not [r for r in db.added if isinstance(r, EmailTarget)]


@pytest.mark.asyncio
async def test_import_without_a_target_name_keeps_the_stored_one(monkeypatch):
    """A payload that carries no name must not blank the one the listing
    stored. Both sources are partial about this field."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [{
            "email_id": 101,
            "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}],
            "targets": [{"target_id": "TGT-9", "dumps": [{"dump_id": "D1"}]}],
        }]}),
    )
    _patch_persistence(monkeypatch)
    db = FakeDB()
    from_listing = EmailTarget(
        case_id=123, target_id="TGT-9", target_name="victim@acme.com"
    )
    db.existing_rows = [from_listing]

    await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert from_listing.email_id == 101
    assert from_listing.target_name == "victim@acme.com"


@pytest.mark.asyncio
async def test_dump_listing_never_blanks_a_stored_name(monkeypatch):
    """The provider's dump listing carries no name at all, so caching it
    must not erase the name the import stored."""
    _install_fake_client(
        monkeypatch, response=FakeResponse(payload=_dumps_payload({"dump_id": "D1"}))
    )
    monkeypatch.setattr(settings, "EMAIL_DUMP_API_BASE_URL", "http://provider:8002")
    existing = EmailDump(case_id=123, target_id="TGT-42", dump_id="D1", name="March dump")
    db = DumpsDB()
    db.target = _target_row()
    db.existing_rows = [existing]

    await list_dumps(123, "TGT-42", "token", db)

    assert existing.name == "March dump"


def test_layer_id_is_required_on_emails():
    """An imported email is always a layer, so an `emails` row may not
    exist without naming one."""
    assert not EmailRecord.__table__.columns["layer_id"].nullable


@pytest.mark.asyncio
async def test_import_gives_every_email_a_layer_the_user_can_see(monkeypatch):
    """Each email in the payload becomes a layer, and every email row
    points at that layer."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [
            {"email_id": 201, "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}]},
            {"email_id": 202, "ips": [{"ip": "1.1.1.1", "latitude": -33.8688, "longitude": 151.2093}]},
        ]}),
    )
    state = _patch_persistence(monkeypatch)
    db = FakeDB()

    result = await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    # Both emails became layers of their own.
    assert result.layers_created == 2
    assert [layer["name"] for layer in state["layers"]] == ["Email 201", "Email 202"]

    # Every email row names the layer of the email it belongs to.
    emails = [r for r in db.added if isinstance(r, EmailRecord)]
    assert len(emails) == 2
    assert all(e.layer_id is not None for e in emails)
    assert {e.layer_id for e in emails} == {1, 2}


@pytest.mark.asyncio
async def test_import_clears_a_stale_layer_link_on_reimport(monkeypatch):
    """Re-importing keeps layer_id current rather than leaving a row
    pointing at a layer it no longer belongs to."""
    _install_fake_client(
        monkeypatch,
        response=FakeResponse(payload={"success": True, "data": [{
            "email_id": 101,
            "ips": [{"ip": "8.8.8.8", "latitude": 18.5204, "longitude": 73.8567}],
        }]}),
    )
    _patch_persistence(monkeypatch, existing_layers={5: {
        "id": 5, "case_id": 123, "name": "Email 101",
        "layer_type": "point", "module_slug": "email-dump", "visible": True,
        "created_at": None,
    }})
    # The layer already exists, so the import reuses it instead of
    # creating a second "Email 101".
    db = FakeDB(existing_layer_ids=[5])
    existing = EmailRecord(case_id=123, email_id=101, ip="8.8.8.8", layer_id=99)
    db.existing_rows = [existing]

    await import_origin_ips(123, EmailDumpOriginIpQuery(), "token", db)

    assert existing.layer_id == 5
