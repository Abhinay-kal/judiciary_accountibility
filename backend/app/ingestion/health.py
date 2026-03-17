"""Health state-machine for ingestion sources.

Maintains the :class:`~app.ingestion.models.IngestionSource` health
status after every run and exposes helper utilities consumed by the
monitor sweep and the manual-override endpoint.

State-transition logic
-----------------------
* ``DISABLED``  — ``source.is_active is False`` (terminal; cleared by
  :func:`resume_source`).
* ``FAILED``    — ``consecutive_failures >= failure_threshold``.
* ``DEGRADED``  — ``parser_confidence_score < confidence_min``,
  **or** the run status was ``RUN_PARTIAL``,
  **but** consecutive failures < threshold.
* ``HEALTHY``   — run succeeded with confidence above minimum.

The function is *pure-functional* with respect to the caller: it
mutates the SQLAlchemy ORM objects that were passed in, but does
**not** commit the session — that is the pipeline's responsibility.

Usage::

    from app.ingestion.health import update_source_health

    update_source_health(source, run, settings)
    db.commit()
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.ingestion.config import IngestionSettings
from app.ingestion.models import (
    HEALTH_DEGRADED,
    HEALTH_DISABLED,
    HEALTH_FAILED,
    HEALTH_HEALTHY,
    RUN_FAILED,
    RUN_PARTIAL,
    RUN_SUCCESS,
    IngestionRun,
    IngestionSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Primary update function
# ---------------------------------------------------------------------------


def update_source_health(
    source: IngestionSource,
    run: IngestionRun,
    settings: IngestionSettings,
) -> str:
    """Update *source* health fields based on the just-completed *run*.

    Parameters
    ----------
    source:
        ORM object to be mutated.
    run:
        The run that just finished (its ``status`` must already be set).
    settings:
        Ingestion settings for threshold constants.

    Returns
    -------
    str
        The new health status string (one of the ``HEALTH_*`` constants).
    """
    now = datetime.now(timezone.utc)
    source.last_attempt_at = now

    # Disabled sources trump everything
    if not source.is_active:
        source.health_status = HEALTH_DISABLED
        return HEALTH_DISABLED

    if run.status == RUN_SUCCESS:
        confidence = run.parser_confidence_score or 1.0
        if confidence < settings.ingest_confidence_min:
            # Technically succeeded but confidence is too low → degraded
            source.consecutive_failures += 1
            source.last_error = (
                f"Low parser confidence: {confidence:.2f} "
                f"(min={settings.ingest_confidence_min})"
            )
            new_status = HEALTH_DEGRADED
        else:
            # Clean success
            source.consecutive_failures = 0
            source.last_success_at = now
            source.last_error = None
            if run.records_fetched is not None:
                source.last_record_count = run.records_fetched
            if run.http_status is not None:
                source.last_http_status = run.http_status
            new_status = HEALTH_HEALTHY

    elif run.status == RUN_PARTIAL:
        # Partially succeeded — increment counter but not as severe
        source.consecutive_failures += 1
        source.last_error = run.error_summary or "Partial run"
        if run.http_status is not None:
            source.last_http_status = run.http_status
        if source.consecutive_failures >= settings.ingest_failure_threshold:
            new_status = HEALTH_FAILED
        else:
            new_status = HEALTH_DEGRADED

    else:  # RUN_FAILED
        source.consecutive_failures += 1
        source.last_error = run.error_summary or "Run failed"
        if run.http_status is not None:
            source.last_http_status = run.http_status
        if source.consecutive_failures >= settings.ingest_failure_threshold:
            new_status = HEALTH_FAILED
        else:
            new_status = HEALTH_DEGRADED

    source.health_status = new_status
    source.failure_count = (source.failure_count or 0) + (
        1 if run.status != RUN_SUCCESS else 0
    )
    logger.info(
        "Source %s health → %s (consecutive_failures=%d)",
        source.source_name,
        new_status,
        source.consecutive_failures,
    )
    return new_status


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def reset_source_health(source: IngestionSource) -> None:
    """Clear failure counters and restore HEALTHY status.

    Does **not** commit the session.
    """
    source.consecutive_failures = 0
    source.failure_count = 0
    source.last_error = None
    source.health_status = HEALTH_HEALTHY


def force_health_status(source: IngestionSource, status: str) -> None:
    """Forcibly set *source* health to *status* (operator override).

    Does **not** commit the session.

    Raises
    ------
    ValueError
        If *status* is not a recognised health constant.
    """
    valid = {HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_FAILED, HEALTH_DISABLED}
    if status not in valid:
        raise ValueError(f"Unknown health status '{status}'. Valid: {valid}")
    source.health_status = status
    logger.warning(
        "Source %s health manually overridden → %s",
        source.source_name,
        status,
    )
