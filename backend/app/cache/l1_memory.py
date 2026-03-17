from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryEntry:
    payload: Any
    cached_at: float
    fresh_until: float
    stale_until: float


class L1MemoryCache:
    """Thread-safe bounded in-memory cache with stale window support."""

    def __init__(self, max_items: int = 5000) -> None:
        self._max_items = max_items
        self._lock = threading.RLock()
        self._data: dict[str, MemoryEntry] = {}
        self._order: list[str] = []

    def get(self, key: str) -> MemoryEntry | None:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            if item.stale_until <= now:
                self._delete_locked(key)
                return None
            self._touch_locked(key)
            return item

    def set(self, key: str, payload: Any, *, fresh_ttl: int, stale_ttl: int) -> None:
        now = time.time()
        entry = MemoryEntry(
            payload=payload,
            cached_at=now,
            fresh_until=now + max(1, fresh_ttl),
            stale_until=now + max(max(1, stale_ttl), max(1, fresh_ttl)),
        )
        with self._lock:
            if key in self._data:
                self._data[key] = entry
                self._touch_locked(key)
                return
            self._data[key] = entry
            self._order.append(key)
            self._evict_locked()

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._data.keys() if key.startswith(prefix)]
            for key in keys:
                self._delete_locked(key)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    def _evict_locked(self) -> None:
        while len(self._order) > self._max_items:
            oldest = self._order.pop(0)
            self._data.pop(oldest, None)

    def _touch_locked(self, key: str) -> None:
        try:
            self._order.remove(key)
        except ValueError:
            pass
        self._order.append(key)

    def _delete_locked(self, key: str) -> None:
        self._data.pop(key, None)
        try:
            self._order.remove(key)
        except ValueError:
            pass
