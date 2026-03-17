from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.cache.keys import build_cache_key, namespace_prefix
from app.cache.l1_memory import L1MemoryCache
from app.cache.metrics import CACHE_L1_SIZE, CACHE_LOOKUP_DURATION_SECONDS, CACHE_STALE_SERVED_TOTAL, CACHE_TIER_HITS_TOTAL, CACHE_TIER_MISSES_TOTAL, UPSTREAM_CALLS_AVOIDED_TOTAL
from app.cache.redis_cache import RedisCache, RedisEnvelope
from app.core.config import get_settings

T = TypeVar("T")


@dataclass
class CacheMeta:
    status: str
    source: str
    cached_at: float | None
    fresh_until: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_status": self.status,
            "source": self.source,
            "cached_at": self.cached_at,
            "fresh_until": self.fresh_until,
        }


class MultiTierCache:
    """L1 in-memory + L2 Redis cache with stale-while-revalidate support."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self.enabled = bool(settings.cache_enabled)
        self._version = settings.cache_key_version
        self._prefix = settings.cache_app_prefix
        self._l1 = L1MemoryCache(max_items=settings.cache_l1_max_items)
        self._l2 = RedisCache(settings.redis_url)

    def _resource_ttls(self, resource: str, fresh_ttl: int | None) -> tuple[int, int]:
        if fresh_ttl is not None:
            fresh = fresh_ttl
        elif resource in {"investigation_page", "survival_curves"}:
            fresh = self._settings.cache_ttl_medium_seconds
        elif resource in {"case", "cases", "case_timeline"}:
            fresh = self._settings.cache_ttl_short_seconds
        else:
            fresh = self._settings.cache_ttl_long_seconds
        stale = max(fresh + 30, int(fresh * self._settings.cache_stale_multiplier))
        return fresh, stale

    def make_key(self, resource: str, identifier: str, params: dict[str, Any] | None = None, tenant: str | None = None) -> str:
        return build_cache_key(
            app_prefix=self._prefix,
            version=self._version,
            resource=resource,
            identifier=identifier,
            params=params,
            tenant=tenant,
        )

    def invalidate_resource(self, resource: str, tenant: str | None = None) -> int:
        prefix = namespace_prefix(app_prefix=self._prefix, version=self._version, resource=resource, tenant=tenant)
        l1_deleted = self._l1.invalidate_prefix(prefix)
        l2_deleted = self._l2.invalidate_prefix(prefix)
        CACHE_L1_SIZE.set(self._l1.size())
        return l1_deleted + l2_deleted

    def get_or_set(
        self,
        *,
        resource: str,
        identifier: str,
        producer: Callable[[], T],
        params: dict[str, Any] | None = None,
        tenant: str | None = None,
        fresh_ttl: int | None = None,
        allow_stale: bool = True,
    ) -> tuple[T, CacheMeta]:
        if not self.enabled:
            value = producer()
            return value, CacheMeta(status="BYPASS", source="live", cached_at=None, fresh_until=None)

        start = time.perf_counter()
        key = self.make_key(resource, identifier, params=params, tenant=tenant)
        fresh, stale = self._resource_ttls(resource, fresh_ttl)
        now = time.time()

        l1 = self._l1.get(key)
        if l1 is not None:
            CACHE_TIER_HITS_TOTAL.labels(tier="L1", resource=resource).inc()
            CACHE_L1_SIZE.set(self._l1.size())
            if now <= l1.fresh_until:
                CACHE_LOOKUP_DURATION_SECONDS.labels(resource=resource).observe(time.perf_counter() - start)
                UPSTREAM_CALLS_AVOIDED_TOTAL.labels(resource=resource).inc()
                return l1.payload, CacheMeta("HIT", "l1", l1.cached_at, l1.fresh_until)
            if allow_stale and now <= l1.stale_until:
                CACHE_STALE_SERVED_TOTAL.labels(resource=resource).inc()
                self._background_refresh(resource, identifier, producer, params, tenant, fresh, stale)
                CACHE_LOOKUP_DURATION_SECONDS.labels(resource=resource).observe(time.perf_counter() - start)
                return l1.payload, CacheMeta("STALE", "l1", l1.cached_at, l1.fresh_until)
        else:
            CACHE_TIER_MISSES_TOTAL.labels(tier="L1", resource=resource).inc()

        l2 = self._l2.get(key)
        if l2 is not None:
            CACHE_TIER_HITS_TOTAL.labels(tier="L2", resource=resource).inc()
            self._l1.set(key, l2.payload, fresh_ttl=max(1, int(l2.fresh_until - now)), stale_ttl=max(1, int(l2.stale_until - now)))
            CACHE_L1_SIZE.set(self._l1.size())
            if now <= l2.fresh_until:
                CACHE_LOOKUP_DURATION_SECONDS.labels(resource=resource).observe(time.perf_counter() - start)
                UPSTREAM_CALLS_AVOIDED_TOTAL.labels(resource=resource).inc()
                return l2.payload, CacheMeta("HIT", "l2", l2.cached_at, l2.fresh_until)
            if allow_stale and now <= l2.stale_until:
                CACHE_STALE_SERVED_TOTAL.labels(resource=resource).inc()
                self._background_refresh(resource, identifier, producer, params, tenant, fresh, stale)
                CACHE_LOOKUP_DURATION_SECONDS.labels(resource=resource).observe(time.perf_counter() - start)
                return l2.payload, CacheMeta("STALE", "l2", l2.cached_at, l2.fresh_until)
        else:
            CACHE_TIER_MISSES_TOTAL.labels(tier="L2", resource=resource).inc()

        value = producer()
        now2 = time.time()
        self._set_levels(key, value, fresh, stale, now2)
        CACHE_LOOKUP_DURATION_SECONDS.labels(resource=resource).observe(time.perf_counter() - start)
        return value, CacheMeta("MISS", "live", now2, now2 + fresh)

    def _set_levels(self, key: str, value: Any, fresh: int, stale: int, now: float) -> None:
        self._l1.set(key, value, fresh_ttl=fresh, stale_ttl=stale)
        CACHE_L1_SIZE.set(self._l1.size())
        self._l2.set(
            key,
            RedisEnvelope(payload=value, cached_at=now, fresh_until=now + fresh, stale_until=now + stale),
            ttl_seconds=stale,
        )

    def _background_refresh(
        self,
        resource: str,
        identifier: str,
        producer: Callable[[], T],
        params: dict[str, Any] | None,
        tenant: str | None,
        fresh: int,
        stale: int,
    ) -> None:
        key = self.make_key(resource, identifier, params=params, tenant=tenant)

        def _refresh() -> None:
            try:
                value = producer()
                now = time.time()
                self._set_levels(key, value, fresh, stale, now)
            except Exception:
                return

        thread = threading.Thread(target=_refresh, daemon=True)
        thread.start()


cache_manager = MultiTierCache()


def get_or_set_json(
    namespace: str,
    key: str,
    producer: Callable[[], T],
    ttl_seconds: int | None = None,
) -> T:
    value, _ = cache_manager.get_or_set(
        resource=namespace,
        identifier=key,
        params={"raw_key": key},
        producer=producer,
        fresh_ttl=ttl_seconds,
    )
    return value


def get_or_set_json_with_meta(
    namespace: str,
    key: str,
    producer: Callable[[], T],
    ttl_seconds: int | None = None,
) -> tuple[T, dict[str, Any]]:
    value, meta = cache_manager.get_or_set(
        resource=namespace,
        identifier=key,
        params={"raw_key": key},
        producer=producer,
        fresh_ttl=ttl_seconds,
    )
    return value, meta.to_dict()


def invalidate_namespace(namespace: str) -> None:
    cache_manager.invalidate_resource(namespace)
