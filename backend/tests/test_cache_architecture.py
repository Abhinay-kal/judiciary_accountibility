from __future__ import annotations

from app.cache import get_or_set_json_with_meta, invalidate_namespace
from app.cache.invalidation import InvalidationEvent, InvalidationRegistry
from app.cache.keys import build_cache_key, params_hash
from app.cache.l1_memory import L1MemoryCache


def test_params_hash_is_stable_for_key_order() -> None:
    left = {"a": 1, "b": 2}
    right = {"b": 2, "a": 1}
    assert params_hash(left) == params_hash(right)


def test_build_cache_key_sanitizes_segments() -> None:
    key = build_cache_key(
        app_prefix="judiciary app",
        version="v1",
        resource="cases/list",
        identifier="id with spaces",
        params={"page": 1},
    )
    assert " " not in key
    assert "/" not in key
    assert key.startswith("judiciary_app:v1:cases_list:id_with_spaces:")


def test_l1_cache_evicts_oldest_entries() -> None:
    cache = L1MemoryCache(max_items=2)
    cache.set("k1", {"v": 1}, fresh_ttl=10, stale_ttl=20)
    cache.set("k2", {"v": 2}, fresh_ttl=10, stale_ttl=20)
    cache.set("k3", {"v": 3}, fresh_ttl=10, stale_ttl=20)

    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    assert cache.get("k3") is not None


def test_multitier_get_or_set_hits_l1_on_second_read() -> None:
    namespace = "test_cases"
    key = "cache-architecture-hit"
    call_count = {"value": 0}

    def producer() -> dict:
        call_count["value"] += 1
        return {"ok": True, "call": call_count["value"]}

    first, meta_first = get_or_set_json_with_meta(namespace, key, producer, ttl_seconds=60)
    second, meta_second = get_or_set_json_with_meta(namespace, key, producer, ttl_seconds=60)

    assert call_count["value"] == 1
    assert first["call"] == 1
    assert second["call"] == 1
    assert meta_first["cache_status"] == "MISS"
    assert meta_second["cache_status"] == "HIT"
    assert meta_second["source"] in {"l1", "l2"}

    invalidate_namespace(namespace)


def test_invalidation_registry_handles_ingestion_completed_event() -> None:
    registry = InvalidationRegistry()
    resources = registry.resources_for_event(InvalidationEvent(reason="INGESTION_COMPLETED"))
    assert "case" in resources
    assert "cases" in resources
    assert "case_timeline" in resources
    assert "investigation_page" in resources
