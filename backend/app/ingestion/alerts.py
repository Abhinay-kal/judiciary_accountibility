"""Alert dispatch for ingestion failures and anomalies.

Supported channels (configured via env/IngestionSettings):
* **SMTP** — email via ``smtplib``; fires when ``ingest_alert_email_to``
  is set.
* **Webhook** — HTTP POST JSON; fires when ``ingest_alert_webhook_url``
  is set.
* **Log escalation** — ``logger.critical()``; always active as a fallback.

Alert types
-----------
* ``stale_source``      — source not fetched within threshold hours
* ``consecutive_failures`` — source hit failure threshold
* ``schema_change``     — schema drift detected
* ``volume_anomaly``    — spike or drop in record count
* ``low_confidence``    — parser confidence below minimum
* ``http_error``        — 4xx / 5xx response received

Usage::

    manager = AlertManager(settings)
    manager.fire(source, "consecutive_failures", details={"count": 5})
"""
from __future__ import annotations

import json
import logging
import smtplib
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any, Optional

import requests as http_requests

from app.ingestion.config import IngestionSettings
from app.ingestion.metrics import INGEST_ALERTS_TOTAL
from app.ingestion.models import IngestionSource

logger = logging.getLogger(__name__)


@dataclass
class _SuppressionState:
    last_sent: datetime
    sent_count: int

ALERT_STALE_SOURCE = "stale_source"
ALERT_CONSECUTIVE_FAILURES = "consecutive_failures"
ALERT_SCHEMA_CHANGE = "schema_change"
ALERT_VOLUME_ANOMALY = "volume_anomaly"
ALERT_LOW_CONFIDENCE = "low_confidence"
ALERT_HTTP_ERROR = "http_error"
ALERT_OUTCOME_OTHER_RATIO = "outcome_other_ratio"
ALERT_OUTCOME_LOW_CONFIDENCE_RATIO = "outcome_low_confidence_ratio"
ALERT_JUDGE_MISSING_RATIO = "judge_missing_ratio"
ALERT_JUDGE_LOW_CONFIDENCE_RATIO = "judge_low_confidence_ratio"

_SEVERITY: dict[str, str] = {
    ALERT_STALE_SOURCE: "warning",
    ALERT_CONSECUTIVE_FAILURES: "critical",
    ALERT_SCHEMA_CHANGE: "warning",
    ALERT_VOLUME_ANOMALY: "warning",
    ALERT_LOW_CONFIDENCE: "warning",
    ALERT_HTTP_ERROR: "error",
    ALERT_OUTCOME_OTHER_RATIO: "warning",
    ALERT_OUTCOME_LOW_CONFIDENCE_RATIO: "warning",
    ALERT_JUDGE_MISSING_RATIO: "warning",
    ALERT_JUDGE_LOW_CONFIDENCE_RATIO: "warning",
}


class AlertManager:
    """Dispatches alerts through all configured channels."""

    def __init__(self, settings: IngestionSettings) -> None:
        self._s = settings
        self._hostname = socket.gethostname()
        self._suppression: dict[tuple[int, str], _SuppressionState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fire(
        self,
        source: IngestionSource,
        alert_type: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Fire an alert for *source* with *alert_type*.

        Channel errors are caught and logged — an alert failure must
        never propagate and kill the ingestion run.
        """
        payload = self._build_payload(source, alert_type, details or {})
        severity = _SEVERITY.get(alert_type, "info")

        if self._is_suppressed(source.id, alert_type):
            logger.info("Alert suppressed for source=%s type=%s", source.source_name, alert_type)
            return

        # Always log
        self._log_alert(source.source_name, alert_type, severity, payload)

        # SMTP
        if self._s.ingest_alert_email_to:
            try:
                self._send_email(source.source_name, alert_type, severity, payload)
                INGEST_ALERTS_TOTAL.labels(
                    source_name=source.source_name,
                    alert_type=alert_type,
                    channel="email",
                ).inc()
            except Exception as exc:
                logger.error("Alert email failed for '%s': %s", source.source_name, exc)

        # Webhook
        if self._s.ingest_alert_webhook_url:
            try:
                self._send_webhook(payload)
                INGEST_ALERTS_TOTAL.labels(
                    source_name=source.source_name,
                    alert_type=alert_type,
                    channel="webhook",
                ).inc()
            except Exception as exc:
                logger.error("Alert webhook failed for '%s': %s", source.source_name, exc)

        INGEST_ALERTS_TOTAL.labels(
            source_name=source.source_name,
            alert_type=alert_type,
            channel="log",
        ).inc()
        self._mark_sent(source.id, alert_type)

    def _is_suppressed(self, source_id: int, alert_type: str) -> bool:
        key = (source_id, alert_type)
        state = self._suppression.get(key)
        if state is None:
            return False
        now = datetime.now(timezone.utc)
        base_minutes = max(1, self._s.ingest_realert_base_minutes)
        max_minutes = max(base_minutes, self._s.ingest_realert_max_minutes)
        delay_minutes = min(max_minutes, base_minutes * (2 ** max(0, state.sent_count - 1)))
        elapsed = (now - state.last_sent).total_seconds() / 60.0
        return elapsed < delay_minutes

    def _mark_sent(self, source_id: int, alert_type: str) -> None:
        key = (source_id, alert_type)
        current = self._suppression.get(key)
        now = datetime.now(timezone.utc)
        if current is None:
            self._suppression[key] = _SuppressionState(last_sent=now, sent_count=1)
            return
        self._suppression[key] = _SuppressionState(last_sent=now, sent_count=current.sent_count + 1)

    # ------------------------------------------------------------------
    # Channel implementations
    # ------------------------------------------------------------------

    def _log_alert(
        self,
        source_name: str,
        alert_type: str,
        severity: str,
        payload: dict,
    ) -> None:
        message = (
            f"[INGEST ALERT:{severity.upper()}] source={source_name} "
            f"type={alert_type} | {json.dumps(payload.get('details', {}))}"
        )
        if severity == "critical":
            logger.critical(message)
        elif severity == "error":
            logger.error(message)
        else:
            logger.warning(message)

    def _send_email(
        self,
        source_name: str,
        alert_type: str,
        severity: str,
        payload: dict,
    ) -> None:
        subject = (
            f"[{severity.upper()}] Ingestion alert: {alert_type} — {source_name}"
        )
        body = json.dumps(payload, indent=2, default=str)
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self._s.ingest_alert_email_from
        msg["To"] = self._s.ingest_alert_email_to

        if self._s.ingest_alert_smtp_tls:
            smtp_cls = smtplib.SMTP_SSL
        else:
            smtp_cls = smtplib.SMTP  # type: ignore[assignment]

        with smtp_cls(  # type: ignore[call-arg]
            self._s.ingest_alert_smtp_host,
            self._s.ingest_alert_smtp_port,
            timeout=10,
        ) as smtp:
            if self._s.ingest_alert_smtp_user:
                smtp.login(
                    self._s.ingest_alert_smtp_user,
                    self._s.ingest_alert_smtp_password,
                )
            smtp.send_message(msg)

    def _send_webhook(self, payload: dict) -> None:
        resp = http_requests.post(
            self._s.ingest_alert_webhook_url,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        source: IngestionSource,
        alert_type: str,
        details: dict[str, Any],
    ) -> dict:
        return {
            "alert_type": alert_type,
            "severity": _SEVERITY.get(alert_type, "info"),
            "source_name": source.source_name,
            "source_health": source.health_status,
            "consecutive_failures": source.consecutive_failures,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": self._hostname,
            "details": details,
        }
