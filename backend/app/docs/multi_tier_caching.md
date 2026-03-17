# Multi-Tier Caching Architecture

This service uses a three-tier cache strategy to reduce API latency and upstream/DB load while keeping data reasonably fresh.

## Cache Tiers

- L1: in-process memory cache (`app/cache/l1_memory.py`)
- L2: Redis distributed cache (`app/cache/redis_cache.py`)
- L3: persistent precomputed aggregates (`court_stats`, `judge_stats`, `state_metrics`, `case_type_metrics`)

Query preference is:

1. L3 precomputed tables (where applicable)
2. L1/L2 API cache
3. Live DB query / compute path

## Keying Strategy

All cache keys are generated centrally in `app/cache/keys.py`:

- Prefix: `cache_app_prefix`
- Version: `cache_key_version`
- Resource namespace
- Identifier
- Hash of normalized params payload

This avoids collisions and supports global invalidation by rotating the version.

## Freshness and SWR

`app/cache/__init__.py` implements stale-while-revalidate:

- Fresh window: request serves cache as `HIT`
- Stale window: request serves stale payload as `STALE` and asynchronously refreshes
- Expired: request computes live payload as `MISS`

Default TTL classes are configurable:

- `cache_ttl_short_seconds`
- `cache_ttl_medium_seconds`
- `cache_ttl_long_seconds`
- `cache_stale_multiplier`

## Invalidation

Use event-driven invalidation via `invalidate_for_event` in `app/core/cache.py`.

Registry mapping lives in `app/cache/invalidation.py` and currently covers:

- `CASE_UPDATED`
- `HEARING_ADDED`
- `INGESTION_COMPLETED`
- `ANALYTICS_RECOMPUTED`
- `MANUAL_OVERRIDE`
- `VERSION_CHANGED`

Manual namespace invalidation is still supported by `invalidate_namespace` for emergency operations.

## Warmup and Precompute Refresh

`app/tasks/cache_tasks.py` contains:

- `refresh_precomputed_cache`: refreshes L3 aggregate tables
- `warmup_hot_case_cache`: warms detail and timeline cache for top-priority cases

Warmup triggers:

- Startup hook in `app/main.py` when `cache_warmup_enabled=true`
- Celery beat schedule in `app/tasks/scheduler.py`:
  - precomputed refresh every 30 minutes
  - hot case warmup every 20 minutes

## Metadata and Observability

API responses using metadata-aware helpers include:

- `cache_status` (`HIT`, `MISS`, `STALE`, `BYPASS`)
- `source` (`l1`, `l2`, `live`)
- `cached_at`
- `fresh_until`

Prometheus metrics are emitted from `app/cache/metrics.py` for:

- tier hit/miss counts
- stale-served counts
- lookup latency
- L1 size
- upstream calls avoided

## Rollout Notes

1. Apply migration `0017_multi_tier_cache_l3_tables`.
2. Ensure Redis is reachable for L2 cache.
3. Set cache env values in deployment config.
4. Verify warmup tasks are active in Celery beat.
5. Monitor hit ratios and stale-served counters after deploy.
