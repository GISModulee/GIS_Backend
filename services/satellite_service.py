import math
from datetime import datetime, timezone

import httpx

from schemas.live_data_schema import GeoJSONFeature, GeoJSONFeatureCollection, PointGeometry, SatellitePosition
from services.live_cache import AsyncTTLCache
from utils.config import settings
from utils.exceptions import BadRequestError, GatewayTimeoutError, ServiceUnavailableError
from utils.logger import logger


class SatelliteService:
    def __init__(self):
        self._tle_cache = AsyncTTLCache[list[tuple[str, str, str]]](
            settings.SATELLITE_TLE_CACHE_TTL_SECONDS
        )
        self._position_cache = AsyncTTLCache[list[SatellitePosition]](
            settings.SATELLITE_POSITION_CACHE_TTL_SECONDS
        )

    async def list_satellites(
        self,
        bbox: str | None = None,
        limit: int | None = None,
    ) -> list[SatellitePosition]:
        max_results = min(limit or settings.SATELLITE_MAX_RESULTS, settings.SATELLITE_MAX_RESULTS)
        positions = await self._position_cache.get_or_refresh(self._propagate_positions)
        filtered = self._filter_bbox(positions, bbox) if bbox else positions
        return filtered[:max_results]

    async def geojson(
        self,
        bbox: str | None = None,
        limit: int | None = None,
    ) -> GeoJSONFeatureCollection:
        satellites = await self.list_satellites(bbox=bbox, limit=limit)
        return GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry=PointGeometry(coordinates=(sat.longitude, sat.latitude)),
                    properties=sat.model_dump(exclude={"longitude", "latitude"}),
                )
                for sat in satellites
            ]
        )

    async def _propagate_positions(self) -> list[SatellitePosition]:
        try:
            import sgp4  # noqa: F401
        except ImportError:
            logger.error("Satellite propagation dependency missing: sgp4")
            raise ServiceUnavailableError("Satellite propagation dependency is not installed")

        tle_records = await self._tle_cache.get_or_refresh(self._fetch_tles)
        now = datetime.now(timezone.utc)
        positions = []
        for name, line1, line2 in tle_records[: settings.SATELLITE_MAX_RESULTS]:
            position = self._propagate(name, line1, line2, now)
            if position is not None:
                positions.append(position)
        logger.info("Satellite positions propagated | count=%s", len(positions))
        return positions

    async def _fetch_tles(self) -> list[tuple[str, str, str]]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(settings.CELESTRAK_TIMEOUT_SECONDS)) as client:
                response = await client.get(settings.CELESTRAK_TLE_URL)
                response.raise_for_status()
                text = response.text
        except httpx.TimeoutException as exc:
            logger.warning("CelesTrak request timed out | error=%s", exc)
            raise GatewayTimeoutError("CelesTrak TLE request timed out")
        except httpx.HTTPStatusError as exc:
            logger.warning("CelesTrak HTTP error | status=%s", exc.response.status_code)
            raise ServiceUnavailableError("CelesTrak satellite feed is unavailable")
        except httpx.RequestError as exc:
            logger.warning("CelesTrak request failed | error=%s", exc)
            raise ServiceUnavailableError("CelesTrak satellite feed is unavailable")

        records = self._parse_tle(text)
        if not records:
            raise ServiceUnavailableError("CelesTrak satellite feed returned no valid TLE records")
        logger.info("CelesTrak TLE records fetched | count=%s", len(records))
        return records

    def _parse_tle(self, text: str) -> list[tuple[str, str, str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        records = []
        index = 0
        while index + 2 < len(lines):
            name, line1, line2 = lines[index], lines[index + 1], lines[index + 2]
            if line1.startswith("1 ") and line2.startswith("2 "):
                records.append((name, line1, line2))
                index += 3
            else:
                index += 1
        return records

    def _propagate(
        self,
        name: str,
        line1: str,
        line2: str,
        when: datetime,
    ) -> SatellitePosition | None:
        try:
            from sgp4.api import Satrec, jday

            satellite = Satrec.twoline2rv(line1, line2)
            jd, fr = jday(
                when.year,
                when.month,
                when.day,
                when.hour,
                when.minute,
                when.second + when.microsecond / 1_000_000,
            )
            error, position_km, _velocity = satellite.sgp4(jd, fr)
            if error != 0:
                return None
            lat, lon, altitude = self._eci_to_geodetic(position_km, jd + fr)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None
            return SatellitePosition(
                name=name,
                norad_id=line1[2:7].strip() or None,
                latitude=lat,
                longitude=lon,
                altitude_km=altitude,
                propagated_at=when,
            )
        except Exception as exc:
            logger.debug("Satellite propagation skipped | name=%s | error=%s", name, exc)
            return None

    def _eci_to_geodetic(self, position_km, jd_ut1: float) -> tuple[float, float, float]:
        x, y, z = position_km
        theta = self._gmst(jd_ut1)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        x_ecef = cos_t * x + sin_t * y
        y_ecef = -sin_t * x + cos_t * y
        z_ecef = z

        earth_radius_km = 6378.137
        flattening = 1 / 298.257223563
        e2 = flattening * (2 - flattening)
        lon = math.atan2(y_ecef, x_ecef)
        p = math.hypot(x_ecef, y_ecef)
        lat = math.atan2(z_ecef, p * (1 - e2))

        for _ in range(5):
            sin_lat = math.sin(lat)
            n = earth_radius_km / math.sqrt(1 - e2 * sin_lat * sin_lat)
            altitude = p / math.cos(lat) - n
            lat = math.atan2(z_ecef, p * (1 - e2 * n / (n + altitude)))

        sin_lat = math.sin(lat)
        n = earth_radius_km / math.sqrt(1 - e2 * sin_lat * sin_lat)
        altitude = p / math.cos(lat) - n
        return math.degrees(lat), ((math.degrees(lon) + 540) % 360) - 180, altitude

    def _gmst(self, jd_ut1: float) -> float:
        t = (jd_ut1 - 2451545.0) / 36525.0
        gmst = (
            280.46061837
            + 360.98564736629 * (jd_ut1 - 2451545.0)
            + 0.000387933 * t * t
            - (t * t * t) / 38710000.0
        )
        return math.radians(gmst % 360)

    def _filter_bbox(self, positions: list[SatellitePosition], bbox: str) -> list[SatellitePosition]:
        try:
            min_lon, min_lat, max_lon, max_lat = [float(part.strip()) for part in bbox.split(",")]
        except ValueError:
            raise BadRequestError("bbox must be minLon,minLat,maxLon,maxLat")
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise BadRequestError("bbox coordinates are outside valid ranges")
        if min_lon > max_lon or min_lat > max_lat:
            raise BadRequestError("bbox minimums must be less than or equal to maximums")
        return [
            sat
            for sat in positions
            if min_lon <= sat.longitude <= max_lon and min_lat <= sat.latitude <= max_lat
        ]


satellite_service = SatelliteService()
