"""Dynamic scheduler for resilient ingestion sources.

:func:`schedule_due_sources` is the entry-point called by the periodic
Celery beat task.  It queries all active, non-disabled
:class:`~app.ingestion.models.IngestionSource` rows, filters those that
are *due* for a run based on their ``expected_update_interval_minutes``
and applies exponential back-off for FAILED sources so they are not
hammered in tight loops.

Back-off formula
----------------
For a source in ``FAILED`` health with ``consecutive_failures = N``::

    effective_interval = expected_interval * 2^N   (capped at 7 days)

Source priority
---------------
Sources with a lower :attr:`~app.ingestion.models.IngestionSource.priority`
number are dispatched first (higher priority = lower integer value,
analogous to Unix process nice-numbers).

Usage::

    # In a Celery task registered in app/tasks/ingestion_tasks.py:
    schedule_due_sources(db)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.models import HEALTH_DISABLED, HEALTH_FAILED, IngestionSource

logger = logging.getLogger(__name__)

_MAX_BACKOFF_MINUTES = 7 * 24 * 60  # 7 days


def schedule_due_sources(
    db: Session,
    settings: Optional[IngestionSettings] = None,
) -> list[int]:
    """Dispatch Celery tasks for all sources that are due for a run.

    Parameters
    ----------
    db:
        Open SQLAlchemy session.
    settings:
        Defaults to ``get_ingestion_settings()``.

    Returns
    -------
    list[int]
        Source IDs for which tasks were enqueued, in dispatch order.
    """
    if settings is None:
        settings = get_ingestion_settings()

    # Import Celery task lazily to avoid circular imports at module load
    from app.tasks.ingestion_tasks import run_single_source  # type: ignore[import]

    now = datetime.now(timezone.utc)

    sources: list[IngestionSource] = (
        db.query(IngestionSource)
        .filter(
            IngestionSource.is_active.is_(True),
            IngestionSource.health_status != HEALTH_DISABLED,
        )
        .order_by(IngestionSource.priority.asc())
        .all()
    )

    dispatched: list[int] = []
    for source in sources:
        if _is_due(source, now):
            run_single_source.apply_async(
                args=[source.id],
                countdown=0,
            )
            dispatched.append(source.id)
            logger.info(
                "Scheduled run for source '%s' (id=%d, health=%s).",
                source.source_name,
                source.id,
                source.health_status,
            )

    logger.info(
        "Scheduler sweep complete: %d/%d sources dispatched.",
        len(dispatched),
        len(sources),
    )
    return dispatched


def _is_due(source: IngestionSource, now: datetime) -> bool:
    """Return True if *source* should be run now."""
    base_interval = source.expected_update_interval_minutes or 60
    effective_interval = _effective_interval(source, base_interval)

    last_attempt = source.last_attempt_at
    if last_attempt is None:
        return True  # Never run → always due

    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(tzinfo=timezone.utc)

    next_due = last_attempt + timedelta(minutes=effective_interval)
    return now >= next_due


def _effective_interval(source: IngestionSource, base_interval: int) -> float:
    """Compute the back-off-adjusted interval in minutes."""
    if source.health_status != HEALTH_FAILED:
        return base_interval
    n = max(source.consecutive_failures or 0, 0)
    backoff = base_interval * (2 ** n)
    return min(backoff, _MAX_BACKOFF_MINUTES)
