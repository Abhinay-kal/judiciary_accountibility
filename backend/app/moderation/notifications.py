from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def send_correction_acknowledgement(*, contact: str, request_id: int) -> None:
    # Production integrations (SMTP/webhooks) should replace this logger call.
    logger.info("Correction request acknowledged: request_id=%s contact=%s", request_id, contact)


def notify_admin_new_correction(*, target_type: str, target_id: int, request_id: int, admin_contact: str) -> None:
    logger.info(
        "New correction request: request_id=%s target=%s:%s admin_contact=%s",
        request_id,
        target_type,
        target_id,
        admin_contact,
    )


def notify_legal_escalation(*, request_id: int, reason: str) -> None:
    logger.warning("Legal escalation: request_id=%s reason=%s", request_id, reason)
