"""Cross-source monitoring sweep.

:func:`run_monitor_sweep` is called periodically by the Celery beat
scheduler.  It inspects every active :class:`~app.ingestion.models.IngestionSource`
and fires alerts via :class:`~app.ingestion.alerts.AlertManager` when
any of the following conditions are met:

* **Stale source** — ``last_success_at`` was more than
  ``ingest_alert_threshold_hours`` hours ago (or never).
* **Consecutive failures** — ``consecutive_failures >=
  ingest_failure_threshold``.
* **Schema change** — the most recent run has
  ``schema_change_detected = True``.
* **Volume anomaly** — the most recent run has
  ``volume_anomaly_detected = True``.
* **Low parser confidence** — latest
  ``parser_confidence_score < ingest_confidence_min``.

The sweep marks sources it has already alerted about to avoid SMTP
flooding: once an alert of a given type has been fired for a source in
the *current* run it is not repeated until the sweep detects the
condition has cleared and returned.

Usage::

    # In a Celery task:
    run_monitor_sweep(db)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.alerts import (
    ALERT_CONSECUTIVE_FAILURES,
    ALERT_JUDGE_LOW_CONFIDENCE_RATIO,
    ALERT_JUDGE_MISSING_RATIO,
    ALERT_LOW_CONFIDENCE,
    ALERT_OUTCOME_LOW_CONFIDENCE_RATIO,
    ALERT_OUTCOME_OTHER_RATIO,
    ALERT_SCHEMA_CHANGE,
    ALERT_STALE_SOURCE,
    ALERT_VOLUME_ANOMALY,
    AlertManager,
)
from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.models import (
    HEALTH_DISABLED,
    RUN_SUCCESS,
    IngestionRun,
    IngestionSource,
)
from app.models import Hearing, HearingOutcomeType
from app.models import JudgeAssignment
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def run_monitor_sweep(
    db: Session,
    settings: Optional[IngestionSettings] = None,
) -> dict[str, list[str]]:
    """Sweep all active sources and fire alerts where needed.

    Parameters
    ----------
    db:
        Open SQLAlchemy session.
    settings:
        Optional override; defaults to ``get_ingestion_settings()``.

    Returns
    -------
    dict[str, list[str]]
        Mapping of ``source_name → list[alert_type]`` for every alert
        that was fired during this sweep.
    """
    if settings is None:
        settings = get_ingestion_settings()
    app_settings = get_settings()

    manager = AlertManager(settings)
    fired: dict[str, list[str]] = {}

    sources: list[IngestionSource] = (
        db.query(IngestionSource)
        .filter(
            IngestionSource.is_active.is_(True),
            IngestionSource.health_status != HEALTH_DISABLED,
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    threshold_seconds = settings.ingest_alert_threshold_hours * 3600

    for source in sources:
        alerts_for_source: list[str] = []

        # ----------------------------------------------------------------
        # 1. Stale source check
        # ----------------------------------------------------------------
        last_ok: Optional[datetime] = source.last_success_at
        if last_ok is None:
            age_seconds = float("inf")
        else:
            # Make last_ok timezone-aware if needed
            if last_ok.tzinfo is None:
                last_ok = last_ok.replace(tzinfo=timezone.utc)
            age_seconds = (now - last_ok).total_seconds()

        if age_seconds > threshold_seconds:
            manager.fire(
                source,
                ALERT_STALE_SOURCE,
                details={
                    "last_success_at": str(last_ok),
                    "age_hours": round(age_seconds / 3600, 2),
                    "threshold_hours": settings.ingest_alert_threshold_hours,
                },
            )
            alerts_for_source.append(ALERT_STALE_SOURCE)

        # ----------------------------------------------------------------
        # 2. Consecutive failures
        # ----------------------------------------------------------------
        if source.consecutive_failures >= settings.ingest_failure_threshold:
            manager.fire(
                source,
                ALERT_CONSECUTIVE_FAILURES,
                details={
                    "consecutive_failures": source.consecutive_failures,
                    "threshold": settings.ingest_failure_threshold,
                    "last_error": source.last_error,
                },
            )
            alerts_for_source.append(ALERT_CONSECUTIVE_FAILURES)

        # ----------------------------------------------------------------
        # Fetch last run for per-run anomaly checks
        # ----------------------------------------------------------------
        last_run: Optional[IngestionRun] = (
            db.query(IngestionRun)
            .filter(IngestionRun.source_id == source.id)
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
        if last_run is None:
            if alerts_for_source:
                fired[source.source_name] = alerts_for_source
            continue

        # ----------------------------------------------------------------
        # 3. Schema change on last run
        # ----------------------------------------------------------------
        if last_run.schema_change_detected:
            manager.fire(
                source,
                ALERT_SCHEMA_CHANGE,
                details={
                    "run_id": last_run.run_id,
                    "started_at": str(last_run.started_at),
                },
            )
            alerts_for_source.append(ALERT_SCHEMA_CHANGE)

        # ----------------------------------------------------------------
        # 4. Volume anomaly on last run
        # ----------------------------------------------------------------
        if last_run.volume_anomaly_detected:
            manager.fire(
                source,
                ALERT_VOLUME_ANOMALY,
                details={
                    "run_id": last_run.run_id,
                    "records_fetched": last_run.records_fetched,
                },
            )
            alerts_for_source.append(ALERT_VOLUME_ANOMALY)

        # ----------------------------------------------------------------
        # 5. Low parser confidence on last run
        # ----------------------------------------------------------------
        conf = last_run.parser_confidence_score
        if conf is not None and conf < settings.ingest_confidence_min:
            manager.fire(
                source,
                ALERT_LOW_CONFIDENCE,
                details={
                    "run_id": last_run.run_id,
                    "confidence_score": conf,
                    "minimum": settings.ingest_confidence_min,
                },
            )
            alerts_for_source.append(ALERT_LOW_CONFIDENCE)

        recent_hearings = (
            db.query(Hearing)
            .filter(Hearing.source == source.source_name, Hearing.is_deleted.is_(False))
            .order_by(Hearing.date.desc())
            .limit(200)
            .all()
        )
        if recent_hearings:
            total_hearings = len(recent_hearings)
            if total_hearings == 0:
                if alerts_for_source:
                    fired[source.source_name] = alerts_for_source
                continue
            other_ratio = sum(1 for hearing in recent_hearings if hearing.outcome_type == HearingOutcomeType.OTHER) / total_hearings
            low_conf_ratio = sum(
                1
                for hearing in recent_hearings
                if (hearing.outcome_confidence or 0.0) < settings.ingest_confidence_min
            ) / total_hearings
            if other_ratio > settings.ingest_outcome_other_alert_ratio:
                manager.fire(
                    source,
                    ALERT_OUTCOME_OTHER_RATIO,
                    details={
                        "other_ratio": round(other_ratio, 4),
                        "threshold": settings.ingest_outcome_other_alert_ratio,
                        "sample_size": total_hearings,
                    },
                )
                alerts_for_source.append(ALERT_OUTCOME_OTHER_RATIO)
            if low_conf_ratio > settings.ingest_outcome_low_confidence_alert_ratio:
                manager.fire(
                    source,
                    ALERT_OUTCOME_LOW_CONFIDENCE_RATIO,
                    details={
                        "low_confidence_ratio": round(low_conf_ratio, 4),
                        "threshold": settings.ingest_outcome_low_confidence_alert_ratio,
                        "sample_size": total_hearings,
                    },
                )
                alerts_for_source.append(ALERT_OUTCOME_LOW_CONFIDENCE_RATIO)

            hearing_ids = [hearing.id for hearing in recent_hearings]
            assignments = (
                db.query(JudgeAssignment)
                .filter(JudgeAssignment.hearing_id.in_(hearing_ids))
                .all()
            )
            assignments_by_hearing: dict[int, list[JudgeAssignment]] = {}
            for assignment in assignments:
                assignments_by_hearing.setdefault(assignment.hearing_id, []).append(assignment)

            missing_ratio = (
                sum(1 for hearing in recent_hearings if hearing.id not in assignments_by_hearing) / total_hearings
            )
            low_conf_ratio = (
                sum(
                    1
                    for hearing in recent_hearings
                    if hearing.id in assignments_by_hearing
                    and min(item.attribution_confidence for item in assignments_by_hearing[hearing.id]) < app_settings.judge_match_confidence_threshold
                )
                / total_hearings
            )

            if missing_ratio > settings.ingest_judge_missing_alert_ratio:
                manager.fire(
                    source,
                    ALERT_JUDGE_MISSING_RATIO,
                    details={
                        "missing_ratio": round(missing_ratio, 4),
                        "threshold": settings.ingest_judge_missing_alert_ratio,
                        "sample_size": total_hearings,
                    },
                )
                alerts_for_source.append(ALERT_JUDGE_MISSING_RATIO)
            if low_conf_ratio > settings.ingest_judge_low_confidence_alert_ratio:
                manager.fire(
                    source,
                    ALERT_JUDGE_LOW_CONFIDENCE_RATIO,
                    details={
                        "low_confidence_ratio": round(low_conf_ratio, 4),
                        "threshold": settings.ingest_judge_low_confidence_alert_ratio,
                        "sample_size": total_hearings,
                    },
                )
                alerts_for_source.append(ALERT_JUDGE_LOW_CONFIDENCE_RATIO)

        if alerts_for_source:
            fired[source.source_name] = alerts_for_source
            logger.info(
                "Monitor sweep fired %d alert(s) for source '%s': %s",
                len(alerts_for_source),
                source.source_name,
                alerts_for_source,
            )

    logger.info(
        "Monitor sweep complete — %d source(s) inspected, %d with alerts.",
        len(sources),
        len(fired),
    )
    return fired
