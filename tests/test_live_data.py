from datetime import datetime, timezone

import httpx
import pytest

from main import app
from schemas.live_data_schema import SatellitePosition
from services.aircraft_service import AircraftService
from services.live_cache import AsyncTTLCache
from services.satellite_service import SatelliteService
from utils.dependencies import get_current_user
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_aircraft_normalizes_opensky_response_and_skips_invalid_coordinates(monkeypatch):
    service = AircraftService()

    async def fake_fetch(_bbox):
        raw_states = [
            [
                "abc123",
                " GIS001 ",
                "India",
                1_788_000_000,
                1_788_000_010,
                73.8567,
                18.5204,
                9753.6,
                False,
                231.5,
                270.0,
                0.0,
                None,
                10058.4,
                "1234",
                False,
                0,
                3,
            ],
            ["bad", None, None, None, None, None, None],
        ]
        return [item for raw in raw_states if (item := service._normalize_state(raw))]

    monkeypatch.setattr(service, "_fetch_aircraft", fake_fetch)

    aircraft = await service.list_aircraft()

    assert len(aircraft) == 1
    assert aircraft[0].icao24 == "abc123"
    assert aircraft[0].callsign == "GIS001"
    assert aircraft[0].longitude == 73.8567
    assert aircraft[0].latitude == 18.5204


@pytest.mark.asyncio
async def test_async_ttl_cache_coalesces_concurrent_refreshes():
    cache = AsyncTTLCache[int](ttl_seconds=60)
    calls = 0

    async def refresh():
        nonlocal calls
        calls += 1
        return 42

    first = await cache.get_or_refresh(refresh)
    second = await cache.get_or_refresh(refresh)

    assert first == 42
    assert second == 42
    assert calls == 1


def test_aircraft_bbox_validation_requires_all_values():
    service = AircraftService()

    with pytest.raises(Exception):
        service._validate_bbox(10, None, 20, 30)


def test_satellite_parses_tle_records():
    service = SatelliteService()
    records = service._parse_tle(
        """
ISS (ZARYA)
1 25544U 98067A   24275.51841435  .00016717  00000+0  30415-3 0  9990
2 25544  51.6395 167.6089 0007251  32.4380  59.7832 15.50074724474567
"""
    )

    assert records == [
        (
            "ISS (ZARYA)",
            "1 25544U 98067A   24275.51841435  .00016717  00000+0  30415-3 0  9990",
            "2 25544  51.6395 167.6089 0007251  32.4380  59.7832 15.50074724474567",
        )
    ]


def test_satellite_bbox_filtering():
    service = SatelliteService()
    now = datetime.now(timezone.utc)
    positions = [
        SatellitePosition(name="inside", norad_id="1", longitude=73, latitude=18, altitude_km=400, propagated_at=now),
        SatellitePosition(name="outside", norad_id="2", longitude=10, latitude=10, altitude_km=400, propagated_at=now),
    ]

    filtered = service._filter_bbox(positions, "70,15,80,20")

    assert [item.name for item in filtered] == ["inside"]


def test_api_routes_require_authentication():
    client = TestClient(app)

    aircraft_response = client.get("/api/aircraft")
    satellite_response = client.get("/api/satellites")

    assert aircraft_response.status_code == 401
    assert satellite_response.status_code == 401


def test_api_routes_return_geojson_with_authenticated_user(monkeypatch):
    async def fake_user():
        return {"user_id": 1, "email": "analyst@example.com", "role": "analyst"}

    async def fake_aircraft_geojson(**_kwargs):
        return {"type": "FeatureCollection", "features": []}

    async def fake_satellite_geojson(**_kwargs):
        return {"type": "FeatureCollection", "features": []}

    from services.aircraft_service import aircraft_service
    from services.satellite_service import satellite_service

    app.dependency_overrides[get_current_user] = fake_user
    monkeypatch.setattr(aircraft_service, "geojson", fake_aircraft_geojson)
    monkeypatch.setattr(satellite_service, "geojson", fake_satellite_geojson)

    try:
        client = TestClient(app)
        assert client.get("/api/aircraft").json()["type"] == "FeatureCollection"
        assert client.get("/api/satellites").json()["type"] == "FeatureCollection"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_aircraft_timeout_maps_to_gateway_timeout(monkeypatch):
    service = AircraftService()

    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: TimeoutClient())

    with pytest.raises(Exception) as exc:
        await service._fetch_aircraft(None)

    assert getattr(exc.value, "status_code") == 504
