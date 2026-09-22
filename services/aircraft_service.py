from datetime import datetime, timezone

import httpx

from schemas.live_data_schema import AircraftState, GeoJSONFeature, GeoJSONFeatureCollection, PointGeometry
from services.live_cache import AsyncTTLCache
from utils.config import settings
from utils.exceptions import BadRequestError, GatewayTimeoutError, ServiceUnavailableError
from utils.logger import logger


OPEN_SKY_STATES_PATH = "/states/all"


class AircraftService:
    def __init__(self):
        self._global_cache = AsyncTTLCache[list[AircraftState]](
            settings.AIRCRAFT_CACHE_TTL_SECONDS
        )
        self._bbox_caches: dict[tuple[float, float, float, float], AsyncTTLCache[list[AircraftState]]] = {}

    async def list_aircraft(
        self,
        lamin: float | None = None,
        lomin: float | None = None,
        lamax: float | None = None,
        lomax: float | None = None,
    ) -> list[AircraftState]:
        bbox = self._validate_bbox(lamin, lomin, lamax, lomax)
        if bbox is None:
            return await self._global_cache.get_or_refresh(lambda: self._fetch_aircraft(None))

        cache = self._bbox_caches.setdefault(
            bbox,
            AsyncTTLCache[list[AircraftState]](settings.AIRCRAFT_CACHE_TTL_SECONDS),
        )
        return await cache.get_or_refresh(lambda: self._fetch_aircraft(bbox))

    async def geojson(
        self,
        lamin: float | None = None,
        lomin: float | None = None,
        lamax: float | None = None,
        lomax: float | None = None,
    ) -> GeoJSONFeatureCollection:
        aircraft = await self.list_aircraft(lamin, lomin, lamax, lomax)
        return GeoJSONFeatureCollection(
            features=[
                GeoJSONFeature(
                    geometry=PointGeometry(coordinates=(item.longitude, item.latitude)),
                    properties=item.model_dump(exclude={"longitude", "latitude"}),
                )
                for item in aircraft
            ]
        )

    async def _fetch_aircraft(
        self,
        bbox: tuple[float, float, float, float] | None,
    ) -> list[AircraftState]:
        params = {}
        if bbox is not None:
            lamin, lomin, lamax, lomax = bbox
            params = {"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax}

        try:
            async with httpx.AsyncClient(
                base_url=settings.OPENSKY_BASE_URL,
                timeout=httpx.Timeout(settings.OPENSKY_TIMEOUT_SECONDS),
            ) as client:
                response = await client.get(OPEN_SKY_STATES_PATH, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("OpenSky request timed out | error=%s", exc)
            raise GatewayTimeoutError("OpenSky request timed out")
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
            logger.warning("OpenSky request failed | error=%s", exc)
            raise ServiceUnavailableError("OpenSky aircraft feed is unavailable")

        states = payload.get("states") if isinstance(payload, dict) else None
        if states is None:
            logger.warning("Malformed OpenSky response: missing states")
            raise ServiceUnavailableError("OpenSky aircraft feed returned malformed data")

        normalized = [item for raw in states if (item := self._normalize_state(raw))]
        logger.info("OpenSky aircraft normalized | count=%s", len(normalized))
        return normalized

    def _normalize_state(self, raw: object) -> AircraftState | None:
        if not isinstance(raw, list) or len(raw) < 17:
            return None
        lon = raw[5]
        lat = raw[6]
        if not self._valid_coordinate(lat, lon):
            return None
        return AircraftState(
            icao24=str(raw[0]),
            callsign=(str(raw[1]).strip() or None) if raw[1] is not None else None,
            origin_country=raw[2],
            time_position=self._unix_to_datetime(raw[3]),
            last_contact=self._unix_to_datetime(raw[4]),
            longitude=float(lon),
            latitude=float(lat),
            barometric_altitude=self._float_or_none(raw[7]),
            on_ground=bool(raw[8]),
            velocity=self._float_or_none(raw[9]),
            heading=self._float_or_none(raw[10]),
            vertical_rate=self._float_or_none(raw[11]),
            geometric_altitude=self._float_or_none(raw[13]),
            squawk=raw[14],
            category=raw[17] if len(raw) > 17 else None,
        )

    def _validate_bbox(self, lamin, lomin, lamax, lomax):
        values = (lamin, lomin, lamax, lomax)
        if all(value is None for value in values):
            return None
        if any(value is None for value in values):
            raise BadRequestError("Bounding box requires lamin, lomin, lamax, and lomax")
        if not (-90 <= lamin <= 90 and -90 <= lamax <= 90 and -180 <= lomin <= 180 and -180 <= lomax <= 180):
            raise BadRequestError("Bounding box coordinates are outside valid ranges")
        if lamin > lamax or lomin > lomax:
            raise BadRequestError("Bounding box minimums must be less than or equal to maximums")
        return (float(lamin), float(lomin), float(lamax), float(lomax))

    def _valid_coordinate(self, lat, lon) -> bool:
        return (
            isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
            and -90 <= float(lat) <= 90
            and -180 <= float(lon) <= 180
        )

    def _float_or_none(self, value):
        return float(value) if isinstance(value, (int, float)) else None

    def _unix_to_datetime(self, value):
        return datetime.fromtimestamp(value, tz=timezone.utc) if isinstance(value, (int, float)) else None


aircraft_service = AircraftService()
