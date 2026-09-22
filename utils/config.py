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

    OPENSKY_BASE_URL: str = "https://opensky-network.org/api"
    OPENSKY_TIMEOUT_SECONDS: float = 10.0
    AIRCRAFT_CACHE_TTL_SECONDS: int = 10

    CELESTRAK_TLE_URL: str = "https://celestrak.org/pub/TLE/catalog.txt"
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
