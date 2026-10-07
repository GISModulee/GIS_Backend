from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str
    MAPSERVER_DATABASE_URL: str = ""

    LOG_DIR: str
    LOG_LEVEL: str
    LOG_JSON: bool
    LOG_MAX_BYTES: int
    LOG_BACKUP_COUNT: int

    GEOCLIP_TOP_K: int
    MAX_FILE_SIZE_MB: int

    ALLOWED_ORIGINS: str

    SECRET_KEY: str

    ALGORITHM: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int

    CI_BASE_URL: str
    MODULE_SLUG: str

    # External Email Dump Backend. Only the origin-IP endpoint is
    # consumed by GIS; the full URL is always built from this base URL
    # so no host/port is hard-coded in service logic. Empty is a valid
    # configuration: the app still starts and only the Email Dump route
    # reports a configuration error.
    EMAIL_DUMP_API_BASE_URL: str = ""
    EMAIL_DUMP_TIMEOUT_SECONDS: float = 30.0

    # External Face Recognition System. FRS owns the camera registry and
    # the person registry; GIS only proxies the two registries and
    # converts their payloads into layers and features. The full URL is
    # always built from this base URL so no host/port is hard-coded in
    # service logic. Empty is a valid configuration: the app still
    # starts and only the Face Recognition System routes report a
    # configuration error.
    FRS_API_BASE_URL: str = ""
    FRS_TIMEOUT_SECONDS: float = 30.0

    OPENSKY_BASE_URL: str = "https://opensky-network.org/api"
    OPENSKY_TIMEOUT_SECONDS: float = 10.0
    AIRCRAFT_CACHE_TTL_SECONDS: int = 10

    # CelesTrak base feed URL. The requested group is appended as a
    # query parameter by the service, so this must not already carry a
    # GROUP value. The legacy static file under /pub/TLE/ now answers
    # 403 and is no longer served.
    CELESTRAK_TLE_URL: str = "https://celestrak.org/NORAD/elements/gp.php?FORMAT=tle"
    CELESTRAK_TIMEOUT_SECONDS: float = 15.0
    SATELLITE_TLE_CACHE_TTL_SECONDS: int = 3600
    SATELLITE_POSITION_CACHE_TTL_SECONDS: int = 5
    SATELLITE_MAX_RESULTS: int = 500

    class Config:
        env_file = ".env"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def LOG_PATH(self) -> Path:
        return Path(self.LOG_DIR)

settings = Settings()
