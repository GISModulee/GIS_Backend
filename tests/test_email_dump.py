import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from database.database import get_db
from schemas.email_dump_schema import EmailDumpOriginIpQuery
from services.email_dump import origin_ips
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
from utils.exceptions import AppException


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
    """Minimal session double: queued layer-id and existing-IP lookups.

    `existing_layer_ids` is consumed one entry per layer lookup, so a
    queued `None` means "no layer found" and a queued id means
    "reuse this layer". `existing_ip_sets` is consumed one entry per
    duplicate-feature lookup.
    """

    def __init__(self, existing_layer_ids=(), existing_ip_sets=()):
        self._layer_ids = list(existing_layer_ids)
        self._ip_sets = list(existing_ip_sets)

    def scalar(self, _stmt):
        return self._layer_ids.pop(0) if self._layer_ids else None

    def scalars(self, _stmt):
        return FakeScalarResult(self._ip_sets.pop(0) if self._ip_sets else [])


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

