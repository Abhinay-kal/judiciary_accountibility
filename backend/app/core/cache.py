from __future__ import annotations

from typing import Callable, TypeVar

from app.cache import get_or_set_json as _new_get_or_set_json
from app.cache import get_or_set_json_with_meta
from app.cache import invalidate_namespace as _new_invalidate_namespace
from app.cache.invalidation import InvalidationEvent, InvalidationRegistry

T = TypeVar("T")
_invalidation_registry = InvalidationRegistry()


def get_or_set_json(namespace: str, key: str, producer: Callable[[], T], ttl_seconds: int | None = None) -> T:
    return _new_get_or_set_json(namespace, key, producer, ttl_seconds=ttl_seconds)


def get_or_set_json_meta(namespace: str, key: str, producer: Callable[[], T], ttl_seconds: int | None = None) -> tuple[T, dict]:
    return get_or_set_json_with_meta(namespace, key, producer, ttl_seconds=ttl_seconds)


def invalidate_namespace(namespace: str) -> None:
    _new_invalidate_namespace(namespace)


def invalidate_for_event(reason: str, entity_type: str | None = None, entity_id: str | None = None) -> None:
    event = InvalidationEvent(reason=reason, entity_type=entity_type, entity_id=entity_id)
    for resource in _invalidation_registry.resources_for_event(event):
        _new_invalidate_namespace(resource)
