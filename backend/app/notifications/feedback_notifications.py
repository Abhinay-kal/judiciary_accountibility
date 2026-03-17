from __future__ import annotations

import logging
import json
from urllib import request

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def notify_feedback_token_sent(*, email: str, feedback_id: str, verify_url: str) -> None:
    logger.info(
        "RtR token dispatched email=%s feedback_id=%s verify_url=%s",
        email,
        feedback_id,
        verify_url,
    )


def notify_feedback_status_change(*, email: str, feedback_id: str, status: str, note: str | None = None) -> None:
    logger.info(
        "RtR status update email=%s feedback_id=%s status=%s note=%s",
        email,
        feedback_id,
        status,
        note,
    )


def notify_pending_feedback_threshold(*, pending_count: int) -> None:
    logger.warning("RtR pending queue threshold reached count=%s", pending_count)


def emit_feedback_published_webhook(payload: dict) -> None:
    cfg = get_settings()
    if not cfg.feedback_webhook_url:
        return
    try:
        req = request.Request(
            cfg.feedback_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=5):
            pass
    except Exception as exc:
        logger.warning("RtR webhook dispatch failed: %s", exc)
