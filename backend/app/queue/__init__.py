from __future__ import annotations

from celery import Celery

from app.queue.config import QUEUE_NAMES, queue_settings, task_queues
from app.queue.routing import route_for_task


def apply_multi_queue_config(celery_app: Celery) -> None:
    celery_app.conf.update(**queue_settings())
    celery_app.conf.task_queues = task_queues()
    celery_app.conf.task_routes = (route_for_task,)


__all__ = ["QUEUE_NAMES", "apply_multi_queue_config"]
