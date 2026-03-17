from __future__ import annotations

from kombu import Exchange, Queue

from app.core.config import get_settings

INGESTION_QUEUE = "ingestion"
PARSING_QUEUE = "parsing"
ANALYTICS_QUEUE = "analytics"
NOTIFICATIONS_QUEUE = "notifications"

QUEUE_NAMES = (
    INGESTION_QUEUE,
    PARSING_QUEUE,
    ANALYTICS_QUEUE,
    NOTIFICATIONS_QUEUE,
)


def task_queues() -> tuple[Queue, ...]:
    exchange = Exchange("justice_tracker", type="direct")
    return (
        Queue(INGESTION_QUEUE, exchange=exchange, routing_key=INGESTION_QUEUE, queue_arguments={"x-max-priority": 10}),
        Queue(PARSING_QUEUE, exchange=exchange, routing_key=PARSING_QUEUE, queue_arguments={"x-max-priority": 10}),
        Queue(ANALYTICS_QUEUE, exchange=exchange, routing_key=ANALYTICS_QUEUE, queue_arguments={"x-max-priority": 10}),
        Queue(NOTIFICATIONS_QUEUE, exchange=exchange, routing_key=NOTIFICATIONS_QUEUE, queue_arguments={"x-max-priority": 10}),
    )


def queue_settings() -> dict[str, int | bool | str]:
    settings = get_settings()
    return {
        "task_default_queue": INGESTION_QUEUE,
        "task_default_exchange": "justice_tracker",
        "task_default_exchange_type": "direct",
        "task_default_routing_key": INGESTION_QUEUE,
        "task_queue_max_priority": 10,
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "task_track_started": True,
        "worker_prefetch_multiplier": 1,
        "task_time_limit": 900,
        "task_soft_time_limit": 600,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_default_priority": 5 if settings.queue_priority_enabled else 0,
        "task_annotations": {
            "app.tasks.ingestion_tasks.run_single_source": {
                "rate_limit": f"{max(1, settings.ingestion_rate_limit_per_minute)}/m",
                "soft_time_limit": 240,
                "time_limit": 300,
            },
            "app.tasks.ingestion.run_daily_ingestion": {"soft_time_limit": 480, "time_limit": 600},
            "app.tasks.hearing_outcomes.*": {"soft_time_limit": 360, "time_limit": 420},
            "app.tasks.judge_reconcile.*": {"soft_time_limit": 360, "time_limit": 420},
            "app.tasks.delay_analytics.*": {"soft_time_limit": 1200, "time_limit": 1500},
            "app.tasks.survival_analytics.*": {"soft_time_limit": 1200, "time_limit": 1500},
            "app.tasks.notifications.*": {"soft_time_limit": 30, "time_limit": 60},
        },
    }
