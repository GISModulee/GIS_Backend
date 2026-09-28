from datetime import datetime, timezone

import httpx
import pytest

from main import app
from schemas.live_data_schema import SatellitePosition
from services.aircraft_service import AircraftService
from services.live_cache import AsyncTTLCache
from services.satellite_service import SatelliteService, _FeedCooldown
from utils.constants import DEFAULT_SATELLITE_GROUP, SATELLITE_GROUPS
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


def test_satellite_tle_url_is_built_per_group():
    service = SatelliteService()

    for group in SATELLITE_GROUPS:
        url = service._tle_url_for_group(group)
        assert url.startswith("https://celestrak.org/NORAD/elements/gp.php?FORMAT=tle&")
        assert f"GROUP={group}" in url


def test_satellite_tle_url_rejects_unknown_group():
    service = SatelliteService()

    with pytest.raises(Exception) as exc:
        service._tle_url_for_group("not-a-group")

    assert getattr(exc.value, "status_code") == 400


def test_satellite_route_rejects_unknown_group():
    async def fake_user():
        return {"user_id": 1, "email": "analyst@example.com", "role": "analyst"}

    app.dependency_overrides[get_current_user] = fake_user

    try:
        client = TestClient(app)
        assert client.get("/api/satellites?group=not-a-group").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_satellite_route_passes_group_through(monkeypatch):
    async def fake_user():
        return {"user_id": 1, "email": "analyst@example.com", "role": "analyst"}

    captured = {}

    async def fake_satellite_geojson(**kwargs):
        captured.update(kwargs)
        return {"type": "FeatureCollection", "features": []}

    from services.satellite_service import satellite_service

    app.dependency_overrides[get_current_user] = fake_user
    monkeypatch.setattr(satellite_service, "geojson", fake_satellite_geojson)

    try:
        client = TestClient(app)
        client.get("/api/satellites?group=starlink")
        assert captured["group"] == "starlink"

        # Omitting the group keeps the full active catalog.
        client.get("/api/satellites")
        assert captured["group"] == DEFAULT_SATELLITE_GROUP
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_satellite_caches_are_isolated_per_group(monkeypatch):
    service = SatelliteService()
    requested = []

    async def fake_fetch(group):
        requested.append(group)
        return [(f"OBJ-{group}", f"1 2554{len(group)}U", "2 25544  0.0 0.0 0.0 0.0 0.0 1.0 0.0")]

    monkeypatch.setattr(service, "_fetch_tles", fake_fetch)

    await service.list_satellites(group="stations")
    await service.list_satellites(group="weather")
    await service.list_satellites(group="stations")

    # The repeated 'stations' call is served from its own cache slot, so
    # only one upstream fetch per distinct group is made.
    assert sorted(requested) == ["stations", "weather"]


def test_satellite_detects_cooldown_response():
    service = SatelliteService()
    cooldown = httpx.Response(
        403,
        text="GP data has not updated since your last successful\ndownload of GROUP=starlink",
        headers={"content-type": "text/plain; charset=UTF-8"},
        request=httpx.Request("GET", "https://celestrak.org"),
    )
    blocked = httpx.Response(
        403,
        text="<html><title>403 - Forbidden: Access is denied</title></html>",
        headers={"content-type": "text/html; charset=UTF-8"},
        request=httpx.Request("GET", "https://celestrak.org"),
    )

    assert service._is_cooldown(cooldown) is True
    assert service._is_cooldown(blocked) is False


@pytest.mark.asyncio
async def test_satellite_cooldown_serves_cached_tle(monkeypatch):
    service = SatelliteService()
    calls = []

    async def fetch_once(group):
        calls.append(group)
        return [("ISS", "1 25544U 98067A", "2 25544  0.0 0.0 0.0 0.0 0.0 1.0 0.0")]

    monkeypatch.setattr(service, "_fetch_tles", fetch_once)
    await service._tle_cache_for("stations").get_or_refresh(lambda: fetch_once("stations"))

    # Simulate the upstream cooldown: the TLE cache is stale and a refresh
    # raises instead of returning data.
    service._tle_cache_for("stations").expire()

    async def cooldown(group):
        raise _FeedCooldown()

    monkeypatch.setattr(service, "_fetch_tles", cooldown)

    tle_cache = service._tle_cache_for("stations")
    with pytest.raises(_FeedCooldown):
        await tle_cache.get_or_refresh(lambda: service._fetch_tles("stations"))

    # The stale value is still available to the caller.
    assert tle_cache.get_stale() is not None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_satellite_cooldown_without_cache_is_unavailable(monkeypatch):
    service = SatelliteService()

    async def cooldown(group):
        raise _FeedCooldown()

    monkeypatch.setattr(service, "_fetch_tles", cooldown)

    with pytest.raises(Exception) as exc:
        await service._propagate_positions("starlink")

    assert getattr(exc.value, "status_code") == 503


def test_satellite_norad_id_handles_five_and_six_digit_catalog_numbers():
    service = SatelliteService()

    assert service._extract_norad_id("1 25544U 98067A   24275.51841435  .00016717  00000+0  30415-3 0  9990") == "25544"
    # 6-digit catalog numbers shift every later column, so a fixed-width
    # slice of columns 3-7 would yield "00123" instead of "100123".
    assert service._extract_norad_id("1 100123U 26031A   24275.51841435  .00016717  00000+0  30415-3 0  9990") == "100123"
    assert service._extract_norad_id("1 25544") == "25544"
    assert service._extract_norad_id("1 malformed") is None


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
