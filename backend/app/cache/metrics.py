from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

CACHE_TIER_HITS_TOTAL = Counter(
    "justice_tracker_cache_tier_hits_total",
    "Cache tier hits",
    ["tier", "resource"],
)
CACHE_TIER_MISSES_TOTAL = Counter(
    "justice_tracker_cache_tier_misses_total",
    "Cache tier misses",
    ["tier", "resource"],
)
CACHE_STALE_SERVED_TOTAL = Counter(
    "justice_tracker_cache_stale_served_total",
    "Stale responses served",
    ["resource"],
)
CACHE_EVICTIONS_TOTAL = Counter(
    "justice_tracker_cache_evictions_total",
    "Cache evictions",
    ["tier", "resource"],
)
CACHE_LOOKUP_DURATION_SECONDS = Histogram(
    "justice_tracker_cache_lookup_duration_seconds",
    "Tiered cache lookup latency",
    ["resource"],
)
CACHE_L1_SIZE = Gauge(
    "justice_tracker_cache_l1_items",
    "Current number of L1 cached objects",
)
UPSTREAM_CALLS_AVOIDED_TOTAL = Counter(
    "justice_tracker_upstream_calls_avoided_total",
    "Estimated upstream calls avoided by cache",
    ["resource"],
)
