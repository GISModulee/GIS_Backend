import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from utils.config import settings
from utils.request_context import get_request_id

os.makedirs("logs", exist_ok=True)


class RequestIdFilter(logging.Filter):
    """Injects the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "thread": record.threadName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _build_formatter() -> logging.Formatter:
    if settings.LOG_JSON:
        return JsonFormatter()
    return logging.Formatter(
        "%(asctime)s | %(levelname)s | req=%(request_id)s | "
        "thread=%(threadName)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_logger() -> logging.Logger:
    settings.LOG_PATH.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("backend")

    # Guard: prevent duplicate handlers on re-import (e.g. reload in dev).
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    formatter = _build_formatter()
    request_filter = RequestIdFilter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(request_filter)

    file_handler = RotatingFileHandler(
        settings.LOG_PATH / "app.log",
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)

    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)

    # Don't let logs bubble up to the root logger and print twice.
    logger.propagate = False

    return logger


# FIX (issue #14 in review): previously this module also called
# logging.basicConfig(...) here, attaching a SECOND, non-rotating
# FileHandler("logs/app.log") to the root logger — a completely
# separate, divergent logging config running alongside the "backend"
# logger above. Since backend.propagate = False, app logs weren't
# duplicated, but any third-party library that logs via the root
# logger was silently writing into a different, never-rotated file.
# Removed. Third-party library logs now fall through to Python's
# default "lastResort" handler (stderr, WARNING+) unless you
# explicitly configure the root logger elsewhere.
logger = setup_logger()
