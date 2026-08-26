from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_TIMEOUT_SECONDS: float = 30.0
    CHAT_HISTORY_LIMIT: int = 12
    CHAT_PENDING_ACTION_TTL_SECONDS: int = 300

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

    class Config:
        env_file = ".env"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def LOG_PATH(self) -> Path:
        return Path(self.LOG_DIR)

settings = Settings()
