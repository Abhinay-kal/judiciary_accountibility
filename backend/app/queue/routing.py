from __future__ import annotations

from typing import Any

from app.queue.config import ANALYTICS_QUEUE, INGESTION_QUEUE, NOTIFICATIONS_QUEUE, PARSING_QUEUE

TASK_ROUTES: dict[str, dict[str, str]] = {
    "app.tasks.ingestion.*": {"queue": INGESTION_QUEUE, "routing_key": INGESTION_QUEUE},
    "app.tasks.ingestion_tasks.*": {"queue": INGESTION_QUEUE, "routing_key": INGESTION_QUEUE},
    "app.tasks.reprocess.*": {"queue": PARSING_QUEUE, "routing_key": PARSING_QUEUE},
    "app.tasks.hearing_outcomes.*": {"queue": PARSING_QUEUE, "routing_key": PARSING_QUEUE},
    "app.tasks.judge_reconcile.*": {"queue": PARSING_QUEUE, "routing_key": PARSING_QUEUE},
    "app.tasks.delay_analytics.*": {"queue": ANALYTICS_QUEUE, "routing_key": ANALYTICS_QUEUE},
    "app.tasks.survival_analytics.*": {"queue": ANALYTICS_QUEUE, "routing_key": ANALYTICS_QUEUE},
    "app.tasks.ml_train.*": {"queue": ANALYTICS_QUEUE, "routing_key": ANALYTICS_QUEUE},
    "app.tasks.importance_recompute.*": {"queue": ANALYTICS_QUEUE, "routing_key": ANALYTICS_QUEUE},
    "app.tasks.cache_tasks.*": {"queue": ANALYTICS_QUEUE, "routing_key": ANALYTICS_QUEUE},
    "app.tasks.notifications.*": {"queue": NOTIFICATIONS_QUEUE, "routing_key": NOTIFICATIONS_QUEUE},
}


def route_for_task(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    options: dict[str, Any],
    task: Any = None,
    **_: Any,
) -> dict[str, str] | None:
    del args, kwargs, task
    explicit_queue = options.get("queue")
    if explicit_queue:
        return None

    for pattern, route in TASK_ROUTES.items():
        if _matches(pattern, name):
            return route
    return None


def _matches(pattern: str, task_name: str) -> bool:
    if pattern.endswith("*"):
        return task_name.startswith(pattern[:-1])
    return pattern == task_name


__all__ = ["TASK_ROUTES", "route_for_task"]
