import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class AsyncTTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._entry: _CacheEntry[T] | None = None
        self._lock = asyncio.Lock()

    def clear(self) -> None:
        self._entry = None

    def get_if_fresh(self) -> T | None:
        if self._entry is None:
            return None
        if time.monotonic() >= self._entry.expires_at:
            return None
        return self._entry.value

    def get_stale(self) -> T | None:
        """Return the last known value regardless of expiry.

        Used when an upstream has no newer data to offer and a slightly
        stale value is preferable to failing the request.
        """
        if self._entry is None:
            return None
        return self._entry.value

    def expire(self) -> None:
        """Mark the current entry stale without discarding its value."""
        if self._entry is not None:
            self._entry.expires_at = 0.0

    async def get_or_refresh(self, refresh: Callable[[], Awaitable[T]]) -> T:
        cached = self.get_if_fresh()
        if cached is not None:
            return cached

        async with self._lock:
            cached = self.get_if_fresh()
            if cached is not None:
                return cached
            value = await refresh()
            self._entry = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + max(0, self.ttl_seconds),
            )
            return value
