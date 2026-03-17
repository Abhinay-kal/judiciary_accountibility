from __future__ import annotations

from dataclasses import dataclass

from celery import chain, signature

from app.core.config import get_settings
from app.queue.config import ANALYTICS_QUEUE, INGESTION_QUEUE, NOTIFICATIONS_QUEUE, PARSING_QUEUE


@dataclass(frozen=True)
class WorkerProfile:
    queue: str
    concurrency: int
    prefetch_multiplier: int
    max_tasks_per_child: int
    soft_time_limit: int
    hard_time_limit: int


def worker_profiles() -> dict[str, WorkerProfile]:
    settings = get_settings()
    return {
        INGESTION_QUEUE: WorkerProfile(
            queue=INGESTION_QUEUE,
            concurrency=max(1, settings.ingestion_worker_count),
            prefetch_multiplier=4,
            max_tasks_per_child=500,
            soft_time_limit=240,
            hard_time_limit=300,
        ),
        PARSING_QUEUE: WorkerProfile(
            queue=PARSING_QUEUE,
            concurrency=max(1, settings.parsing_worker_count),
            prefetch_multiplier=2,
            max_tasks_per_child=200,
            soft_time_limit=360,
            hard_time_limit=420,
        ),
        ANALYTICS_QUEUE: WorkerProfile(
            queue=ANALYTICS_QUEUE,
            concurrency=max(1, settings.analytics_worker_count),
            prefetch_multiplier=1,
            max_tasks_per_child=50,
            soft_time_limit=1200,
            hard_time_limit=1500,
        ),
        NOTIFICATIONS_QUEUE: WorkerProfile(
            queue=NOTIFICATIONS_QUEUE,
            concurrency=max(1, settings.notification_worker_count),
            prefetch_multiplier=8,
            max_tasks_per_child=1000,
            soft_time_limit=60,
            hard_time_limit=90,
        ),
    }


def worker_command(queue: str) -> str:
    profile = worker_profiles()[queue]
    return (
        "celery -A app.celery_app.celery_app worker "
        f"-Q {profile.queue} -c {profile.concurrency} --prefetch-multiplier={profile.prefetch_multiplier} "
        f"--max-tasks-per-child={profile.max_tasks_per_child} --soft-time-limit={profile.soft_time_limit} "
        f"--time-limit={profile.hard_time_limit} -n {profile.queue}@%h"
    )


def pipeline_signature(source_id: int, job_id: str) -> chain:
    """Build canonical ingestion->parsing->analytics->notifications pipeline."""

    return chain(
        signature("app.tasks.ingestion_tasks.run_single_source", args=(source_id,), immutable=True).set(
            queue=INGESTION_QUEUE,
            priority=9,
        ),
        signature("app.tasks.hearing_outcomes.reprocess_hearing_outcomes", immutable=True).set(
            queue=PARSING_QUEUE,
            priority=5,
        ),
        signature("app.tasks.delay_analytics.run_delay_analytics_pipeline", immutable=True).set(
            queue=ANALYTICS_QUEUE,
            priority=3,
        ),
        signature(
            "app.tasks.notifications.notify_pipeline_completion",
            kwargs={"job_id": job_id, "source_id": source_id},
            immutable=True,
        ).set(
            queue=NOTIFICATIONS_QUEUE,
            priority=9,
        ),
    )


__all__ = ["WorkerProfile", "worker_profiles", "worker_command", "pipeline_signature"]
