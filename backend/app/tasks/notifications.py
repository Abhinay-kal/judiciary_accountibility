from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.core.config import get_settings
from app.notifications.feedback_notifications import (
    emit_feedback_published_webhook,
    notify_feedback_status_change,
    notify_feedback_token_sent,
)
from app.queue.retry import IdempotencyGuard, RETRY_POLICIES, retry_countdown

logger = logging.getLogger(__name__)
settings = get_settings()
_guard = IdempotencyGuard(settings.celery_broker_url)


@celery_app.task(name="app.tasks.notifications.send_feedback_token_notification", bind=True, max_retries=RETRY_POLICIES["notifications"].max_retries)
def send_feedback_token_notification(self, *, email: str, feedback_id: str, verify_url: str, job_id: str | None = None) -> dict:
    key = f"notif:token:{job_id or feedback_id}"
    if not _guard.claim(key, ttl_seconds=3600):
        return {"status": "duplicate", "key": key}

    try:
        notify_feedback_token_sent(email=email, feedback_id=feedback_id, verify_url=verify_url)
        return {"status": "sent", "feedback_id": feedback_id}
    except Exception as exc:
        if self.request.retries < RETRY_POLICIES["notifications"].max_retries:
            raise self.retry(exc=exc, countdown=retry_countdown("notifications", self.request.retries))
        raise


@celery_app.task(name="app.tasks.notifications.send_feedback_status_notification", bind=True, max_retries=RETRY_POLICIES["notifications"].max_retries)
def send_feedback_status_notification(self, *, email: str, feedback_id: str, status: str, note: str | None = None, job_id: str | None = None) -> dict:
    key = f"notif:status:{job_id or f'{feedback_id}:{status}'}"
    if not _guard.claim(key, ttl_seconds=1800):
        return {"status": "duplicate", "key": key}

    try:
        notify_feedback_status_change(email=email, feedback_id=feedback_id, status=status, note=note)
        return {"status": "sent", "feedback_id": feedback_id, "state": status}
    except Exception as exc:
        if self.request.retries < RETRY_POLICIES["notifications"].max_retries:
            raise self.retry(exc=exc, countdown=retry_countdown("notifications", self.request.retries))
        raise


@celery_app.task(name="app.tasks.notifications.dispatch_feedback_webhook", bind=True, max_retries=RETRY_POLICIES["notifications"].max_retries)
def dispatch_feedback_webhook(self, *, payload: dict, job_id: str | None = None) -> dict:
    key = f"notif:webhook:{job_id or payload.get('id', 'unknown')}"
    if not _guard.claim(key, ttl_seconds=900):
        return {"status": "duplicate", "key": key}

    try:
        emit_feedback_published_webhook(payload)
        return {"status": "sent"}
    except Exception as exc:
        if self.request.retries < RETRY_POLICIES["notifications"].max_retries:
            raise self.retry(exc=exc, countdown=retry_countdown("notifications", self.request.retries))
        raise


@celery_app.task(name="app.tasks.notifications.notify_pipeline_completion", bind=True, max_retries=RETRY_POLICIES["notifications"].max_retries)
def notify_pipeline_completion(self, *, job_id: str, source_id: int) -> dict:
    key = f"pipeline:notify:{job_id}"
    if not _guard.claim(key, ttl_seconds=7200):
        return {"status": "duplicate", "job_id": job_id}

    logger.info("Pipeline completed job_id=%s source_id=%s", job_id, source_id)
    return {"status": "ok", "job_id": job_id, "source_id": source_id}
