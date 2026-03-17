from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    base_delay_seconds: int
    max_delay_seconds: int
    exponential: bool = True
    jitter: bool = True


RETRY_POLICIES: dict[str, RetryPolicy] = {
    "ingestion": RetryPolicy(max_retries=6, base_delay_seconds=10, max_delay_seconds=600),
    "parsing": RetryPolicy(max_retries=3, base_delay_seconds=5, max_delay_seconds=120),
    "analytics": RetryPolicy(max_retries=0, base_delay_seconds=0, max_delay_seconds=0),
    "notifications": RetryPolicy(max_retries=5, base_delay_seconds=2, max_delay_seconds=60),
}


def retry_countdown(queue_name: str, retries: int) -> int:
    policy = RETRY_POLICIES.get(queue_name, RETRY_POLICIES["parsing"])
    if policy.max_retries == 0:
        return 0

    step = max(0, int(retries))
    if policy.exponential:
        delay = policy.base_delay_seconds * (2 ** step)
    else:
        delay = policy.base_delay_seconds
    delay = min(delay, policy.max_delay_seconds)

    if policy.jitter and delay > 0:
        jitter_cap = max(1, int(delay * 0.2))
        delay += random.randint(0, jitter_cap)
    return int(delay)


class IdempotencyGuard:
    """Best-effort task dedupe guard supporting Redis with in-process fallback."""

    _fallback_lock = threading.RLock()
    _fallback_seen: dict[str, float] = {}

    def __init__(self, redis_url: str | None) -> None:
        self._redis = None
        if redis_url and redis is not None:
            try:
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._redis = None

    def claim(self, key: str, ttl_seconds: int = 3600) -> bool:
        if not key:
            return False

        if self._redis is not None:
            try:
                created = self._redis.set(key, "1", nx=True, ex=max(30, ttl_seconds))
                return bool(created)
            except Exception:
                pass

        now = time.time()
        expire_at = now + max(30, ttl_seconds)
        with self._fallback_lock:
            stale = [k for k, v in self._fallback_seen.items() if v <= now]
            for item in stale:
                self._fallback_seen.pop(item, None)
            if key in self._fallback_seen:
                return False
            self._fallback_seen[key] = expire_at
            return True


__all__ = ["RetryPolicy", "RETRY_POLICIES", "retry_countdown", "IdempotencyGuard"]
