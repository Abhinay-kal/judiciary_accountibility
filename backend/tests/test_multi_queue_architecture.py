from __future__ import annotations

from app.queue.config import ANALYTICS_QUEUE, INGESTION_QUEUE, NOTIFICATIONS_QUEUE, PARSING_QUEUE
from app.queue.retry import RETRY_POLICIES, IdempotencyGuard, retry_countdown
from app.queue.routing import route_for_task
from app.queue.workers import pipeline_signature


def test_task_routing_correctness() -> None:
    assert route_for_task("app.tasks.ingestion.run_daily_ingestion", (), {}, {}) == {
        "queue": INGESTION_QUEUE,
        "routing_key": INGESTION_QUEUE,
    }
    assert route_for_task("app.tasks.hearing_outcomes.reprocess_hearing_outcomes", (), {}, {}) == {
        "queue": PARSING_QUEUE,
        "routing_key": PARSING_QUEUE,
    }
    assert route_for_task("app.tasks.delay_analytics.run_delay_analytics_pipeline", (), {}, {}) == {
        "queue": ANALYTICS_QUEUE,
        "routing_key": ANALYTICS_QUEUE,
    }
    assert route_for_task("app.tasks.notifications.notify_pipeline_completion", (), {}, {}) == {
        "queue": NOTIFICATIONS_QUEUE,
        "routing_key": NOTIFICATIONS_QUEUE,
    }


def test_retry_behavior_by_queue() -> None:
    ingest_0 = retry_countdown("ingestion", 0)
    ingest_1 = retry_countdown("ingestion", 1)
    notify_0 = retry_countdown("notifications", 0)

    assert ingest_1 >= ingest_0
    assert notify_0 >= 0
    assert RETRY_POLICIES["analytics"].max_retries == 0


def test_failure_isolation_routing_independence() -> None:
    analytics_route = route_for_task("app.tasks.ml_train.retrain_duration_model", (), {}, {})
    ingestion_route = route_for_task("app.tasks.ingestion_tasks.run_ingestion_scheduler", (), {}, {})

    assert analytics_route is not None and analytics_route["queue"] == ANALYTICS_QUEUE
    assert ingestion_route is not None and ingestion_route["queue"] == INGESTION_QUEUE


def test_pipeline_execution_order() -> None:
    sig = pipeline_signature(source_id=1, job_id="job-12345678")
    names = [item.task for item in sig.tasks]
    assert names == [
        "app.tasks.ingestion_tasks.run_single_source",
        "app.tasks.hearing_outcomes.reprocess_hearing_outcomes",
        "app.tasks.delay_analytics.run_delay_analytics_pipeline",
        "app.tasks.notifications.notify_pipeline_completion",
    ]


def test_idempotency_guard() -> None:
    guard = IdempotencyGuard(redis_url=None)
    key = "test:job:1"
    assert guard.claim(key, ttl_seconds=300) is True
    assert guard.claim(key, ttl_seconds=300) is False
