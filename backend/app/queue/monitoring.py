from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from app.core.config import get_settings

try:
    import redis
except Exception:  # pragma: no cover
    redis = None

QUEUE_DEPTH = Gauge("justice_tracker_queue_depth", "Current queue depth", ["queue"])
QUEUE_CONSUMERS = Gauge("justice_tracker_queue_consumers", "Current queue consumers", ["queue"])
QUEUE_FAILURES = Counter("justice_tracker_queue_failures_total", "Queue task failures", ["queue"])
QUEUE_PROCESSED = Counter("justice_tracker_queue_processed_total", "Queue task completions", ["queue"])
QUEUE_LATENCY = Histogram("justice_tracker_queue_latency_seconds", "Queue task runtime", ["queue"])


@dataclass
class QueueStatus:
    queue: str
    depth: int
    consumers: int
    paused: bool = False


class QueueMonitor:
    def __init__(self, broker_url: str | None) -> None:
        self._redis = None
        if broker_url and redis is not None:
            try:
                self._redis = redis.Redis.from_url(broker_url, decode_responses=True)
            except Exception:
                self._redis = None

    def queue_depth(self, queue: str) -> int:
        if self._redis is None:
            return -1
        try:
            return int(self._redis.llen(queue))
        except Exception:
            return -1

    def is_ingestion_paused(self) -> bool:
        if self._redis is None:
            return False
        try:
            return self._redis.get("queue:ingestion:paused") == "1"
        except Exception:
            return False

    def set_ingestion_paused(self, paused: bool) -> None:
        if self._redis is None:
            return
        try:
            if paused:
                self._redis.set("queue:ingestion:paused", "1", ex=86400)
            else:
                self._redis.delete("queue:ingestion:paused")
        except Exception:
            return


def collect_queue_status(celery_app: Any, queues: list[str]) -> list[QueueStatus]:
    settings = get_settings()
    monitor = QueueMonitor(settings.redis_url)

    consumers_by_queue: dict[str, int] = {queue: 0 for queue in queues}
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        active_queues = inspect.active_queues() or {}
        for worker_queues in active_queues.values():
            for item in worker_queues:
                name = item.get("name")
                if name in consumers_by_queue:
                    consumers_by_queue[name] += 1
    except Exception:
        pass

    statuses: list[QueueStatus] = []
    for queue in queues:
        depth = monitor.queue_depth(queue)
        paused = queue == "ingestion" and monitor.is_ingestion_paused()
        status = QueueStatus(
            queue=queue,
            depth=depth,
            consumers=consumers_by_queue.get(queue, 0),
            paused=paused,
        )
        statuses.append(status)

        QUEUE_DEPTH.labels(queue=queue).set(max(0, depth))
        QUEUE_CONSUMERS.labels(queue=queue).set(status.consumers)

    return statuses


def apply_ingestion_backpressure(celery_app: Any, max_depth: int = 2000) -> bool:
    """Pause ingestion scheduler dispatch when queue backlog crosses threshold."""

    settings = get_settings()
    monitor = QueueMonitor(settings.redis_url)
    depth = monitor.queue_depth("ingestion")
    overloaded = depth >= max_depth if depth >= 0 else False

    if overloaded:
        monitor.set_ingestion_paused(True)
    elif monitor.is_ingestion_paused() and depth >= 0 and depth < max(100, max_depth // 3):
        monitor.set_ingestion_paused(False)

    return monitor.is_ingestion_paused()


class QueueLatencyTimer:
    def __init__(self, queue: str) -> None:
        self._queue = queue
        self._start = time.perf_counter()

    def done(self, success: bool = True) -> None:
        elapsed = time.perf_counter() - self._start
        QUEUE_LATENCY.labels(queue=self._queue).observe(elapsed)
        if success:
            QUEUE_PROCESSED.labels(queue=self._queue).inc()
        else:
            QUEUE_FAILURES.labels(queue=self._queue).inc()


__all__ = [
    "QueueStatus",
    "QueueMonitor",
    "collect_queue_status",
    "apply_ingestion_backpressure",
    "QueueLatencyTimer",
]
