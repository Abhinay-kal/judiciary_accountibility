from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


@dataclass
class RedisEnvelope:
    payload: Any
    cached_at: float
    fresh_until: float
    stale_until: float


class RedisCache:
    """L2 distributed cache wrapper with graceful degradation."""

    def __init__(self, redis_url: str | None) -> None:
        self._enabled = bool(redis_url and redis is not None)
        self._client = None
        if self._enabled:
            try:
                self._client = redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get(self, key: str) -> RedisEnvelope | None:
        if not self._enabled or self._client is None:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            obj = json.loads(raw)
            return RedisEnvelope(
                payload=obj.get("payload"),
                cached_at=float(obj.get("cached_at", 0.0)),
                fresh_until=float(obj.get("fresh_until", 0.0)),
                stale_until=float(obj.get("stale_until", 0.0)),
            )
        except Exception:
            return None

    def set(self, key: str, envelope: RedisEnvelope, *, ttl_seconds: int) -> None:
        if not self._enabled or self._client is None:
            return
        try:
            payload = {
                "payload": envelope.payload,
                "cached_at": envelope.cached_at,
                "fresh_until": envelope.fresh_until,
                "stale_until": envelope.stale_until,
            }
            self._client.setex(key, max(1, ttl_seconds), json.dumps(payload, default=str))
        except Exception:
            return

    def invalidate_prefix(self, prefix: str) -> int:
        if not self._enabled or self._client is None:
            return 0
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=f"{prefix}*", count=200)
                if keys:
                    deleted += self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            return deleted
        return deleted
