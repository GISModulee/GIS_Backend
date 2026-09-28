import math
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from schemas.live_data_schema import GeoJSONFeature, GeoJSONFeatureCollection, PointGeometry, SatellitePosition
from services.live_cache import AsyncTTLCache
from utils.config import settings
from utils.constants import (
    CELESTRAK_COOLDOWN_MARKER,
    CELESTRAK_COOLDOWN_STATUS,
    DEFAULT_SATELLITE_GROUP,
    SATELLITE_GROUPS,
)
from utils.exceptions import BadRequestError, GatewayTimeoutError, ServiceUnavailableError
from utils.logger import logger


class _FeedCooldown(Exception):
    """Upstream has no newer TLE data for the requested group.

    Internal control flow only. CelesTrak regenerates GP data on a coarse
    cadence and reports requests made inside that window as a 403. The
    caller reuses the last good TLE set; this never reaches a client.
    """


class SatelliteService:
    def __init__(self):
        # One cache per group per tier. Keyed caches rather than a single
        # slot so that a cold or slow group (starlink) neither blocks nor
        # invalidates the other groups, and each group refreshes on its
        # own clock. The group set is a fixed whitelist, so these dicts
        # are bounded.
        self._tle_caches: dict[str, AsyncTTLCache[list[tuple[str, str, str]]]] = {}
        self._position_caches: dict[str, AsyncTTLCache[list[SatellitePosition]]] = {}

    def _tle_cache_for(self, group: str) -> AsyncTTLCache[list[tuple[str, str, str]]]:
        return self._tle_caches.setdefault(
            group,
            AsyncTTLCache[list[tuple[str, str, str]]](
                settings.SATELLITE_TLE_CACHE_TTL_SECONDS
            ),
        )

    def _position_cache_for(self, group: str) -> AsyncTTLCache[list[SatellitePosition]]:
        return self._position_caches.setdefault(
            group,
            AsyncTTLCache[list[SatellitePosition]](
                settings.SATELLITE_POSITION_CACHE_TTL_SECONDS
            ),
        )

    def _tle_url_for_group(self, group: str) -> str:
        if group not in SATELLITE_GROUPS:
            raise BadRequestError(
                f"Unsupported satellite group: {group}. "
                f"Expected one of {', '.join(sorted(SATELLITE_GROUPS))}."
            )
        base = settings.CELESTRAK_TLE_URL
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}{urlencode({'GROUP': group})}"

    async def list_satellites(
        self,
        bbox: str | None = None,
        limit: int | None = None,
        group: str = DEFAULT_SATELLITE_GROUP,
    ) -> list[SatellitePosition]:
        max_results = min(limit or settings.SATELLITE_MAX_RESULTS, settings.SATELLITE_MAX_RESULTS)
        positions = await self._position_cache_for(group).get_or_refresh(
            lambda: self._propagate_positions(group)
        )
        filtered = self._filter_bbox(positions, bbox) if bbox else positions
        return filtered[:max_results]

    async def geojson(
        self,
        bbox: str | None = None,
        limit: int | None = None,
        group: str = DEFAULT_SATELLITE_GROUP,
    ) -> GeoJSONFeatureCollection:
        satellites = await self.list_satellites(bbox=bbox, limit=limit, group=group)
        return GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry=PointGeometry(coordinates=(sat.longitude, sat.latitude)),
                    properties=sat.model_dump(exclude={"longitude", "latitude"}),
                )
                for sat in satellites
            ]
        )

    async def _propagate_positions(self, group: str) -> list[SatellitePosition]:
        try:
            import sgp4  # noqa: F401
        except ImportError:
            logger.error("Satellite propagation dependency missing: sgp4")
            raise ServiceUnavailableError("Satellite propagation dependency is not installed")

        tle_cache = self._tle_cache_for(group)
        try:
            tle_records = await tle_cache.get_or_refresh(lambda: self._fetch_tles(group))
        except _FeedCooldown:
            tle_records = tle_cache.get_stale()
            if tle_records is None:
                logger.warning("CelesTrak cooldown with no cached TLE | group=%s", group)
                raise ServiceUnavailableError("CelesTrak satellite feed is unavailable")
            logger.info("CelesTrak cooldown, serving cached TLE | group=%s", group)

        now = datetime.now(timezone.utc)
        positions = []
        failed = 0
        for name, line1, line2 in tle_records[: settings.SATELLITE_MAX_RESULTS]:
            position = self._propagate(name, line1, line2, now)
            if position is None:
                failed += 1
            else:
                positions.append(position)
        if failed:
            logger.warning("Satellite propagation dropped records | group=%s | dropped=%s", group, failed)
        logger.info("Satellite positions propagated | group=%s | count=%s", group, len(positions))
        return positions

    async def _fetch_tles(self, group: str) -> list[tuple[str, str, str]]:
        url = self._tle_url_for_group(group)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(settings.CELESTRAK_TIMEOUT_SECONDS)) as client:
                response = await client.get(url)
                if self._is_cooldown(response):
                    logger.info("CelesTrak reports no new data | group=%s", group)
                    raise _FeedCooldown()
                response.raise_for_status()
                text = response.text
        except _FeedCooldown:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("CelesTrak request timed out | group=%s | error=%s", group, exc)
            raise GatewayTimeoutError("CelesTrak TLE request timed out")
        except httpx.HTTPStatusError as exc:
            logger.warning("CelesTrak HTTP error | group=%s | status=%s", group, exc.response.status_code)
            raise ServiceUnavailableError("CelesTrak satellite feed is unavailable")
        except httpx.RequestError as exc:
            logger.warning("CelesTrak request failed | group=%s | error=%s", group, exc)
            raise ServiceUnavailableError("CelesTrak satellite feed is unavailable")

        records = self._parse_tle(text)
        if not records:
            raise ServiceUnavailableError("CelesTrak satellite feed returned no valid TLE records")
        logger.info("CelesTrak TLE records fetched | group=%s | count=%s", group, len(records))
        return records

    @staticmethod
    def _is_cooldown(response: httpx.Response) -> bool:
        """Distinguish CelesTrak's "no new data" 403 from a blocked request.

        The cooldown response is plain text describing the pending
        regeneration; a blocked request returns an HTML error page. Only
        the former is safe to treat as a successful empty update.
        """
        if response.status_code != CELESTRAK_COOLDOWN_STATUS:
            return False
        content_type = response.headers.get("content-type", "")
        if "text/plain" not in content_type:
            return False
        return CELESTRAK_COOLDOWN_MARKER in response.text

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
                norad_id=self._extract_norad_id(line1),
                latitude=lat,
                longitude=lon,
                altitude_km=altitude,
                propagated_at=when,
            )
        except Exception as exc:
            logger.debug("Satellite propagation skipped | name=%s | error=%s", name, exc)
            return None

    @staticmethod
    def _extract_norad_id(line1: str) -> str | None:
        """Read the catalog number out of a TLE line 1.

        Legacy TLEs carry a 5-digit catalog number in columns 3-7. Objects
        cataloged after the 5-digit space was exhausted carry 6 digits,
        which shifts every following column, so a fixed-width slice would
        silently truncate them. The number is instead read from the
        whitespace-delimited field and the trailing classification letter
        removed, which is correct for both widths.
        """
        fields = line1.split()
        if len(fields) < 2:
            return None
        field = fields[1]
        number = field[:-1] if field[-1:].isalpha() else field
        return number if number.isdigit() else None

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
