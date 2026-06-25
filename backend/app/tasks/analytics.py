from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


AGGREGATION_UPSERT_SQL = text(
    """
    WITH hearing_counts AS (
        SELECT
            h.case_id,
            COUNT(*)::int AS hearing_count
        FROM hearings h
        WHERE h.is_deleted IS FALSE
        GROUP BY h.case_id
    ),
    adjournment_counts AS (
        SELECT
            a.case_id,
            COUNT(*)::int AS adjournment_count
        FROM adjournments a
        WHERE a.is_deleted IS FALSE
          AND a.is_adjournment IS TRUE
        GROUP BY a.case_id
    ),
    case_gaps AS (
        SELECT
            c.id AS case_id,
            c.court_id,
            EXTRACT(EPOCH FROM (
                h.date - LAG(h.date) OVER (PARTITION BY h.case_id ORDER BY h.date)
            )) / 86400.0 AS gap_days
        FROM hearings h
        JOIN cases c ON c.id = h.case_id
        WHERE h.is_deleted IS FALSE
          AND c.is_deleted IS FALSE
          AND h.date IS NOT NULL
    ),
    case_medians AS (
        SELECT
            cg.case_id,
            cg.court_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cg.gap_days) AS median_gap_days
        FROM case_gaps cg
        WHERE cg.gap_days IS NOT NULL
          AND cg.gap_days >= 0
        GROUP BY cg.case_id, cg.court_id
    ),
    per_case AS (
        SELECT
            c.id AS case_id,
            c.court_id,
            COALESCE(ac.adjournment_count, 0)::float / NULLIF(hc.hearing_count, 0)::float AS adjournment_rate,
            cm.median_gap_days
        FROM cases c
        JOIN hearing_counts hc ON hc.case_id = c.id
        LEFT JOIN adjournment_counts ac ON ac.case_id = c.id
        LEFT JOIN case_medians cm ON cm.case_id = c.id
        WHERE c.is_deleted IS FALSE
          AND hc.hearing_count > 0
    ),
    per_court AS (
        SELECT
            pc.court_id,
            AVG(pc.adjournment_rate) AS mean_adjournment_rate,
            COALESCE(STDDEV_SAMP(pc.adjournment_rate), 0.0) AS std_dev_adjournment_rate,
            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pc.median_gap_days), 0.0) AS median_time_between_hearings_days
        FROM per_case pc
        GROUP BY pc.court_id
    )
    INSERT INTO court_analytical_snapshots (
        court_id,
        mean_adjournment_rate,
        std_dev_adjournment_rate,
        median_time_between_hearings_days,
        calculated_at
    )
    SELECT
        p.court_id,
        p.mean_adjournment_rate,
        p.std_dev_adjournment_rate,
        p.median_time_between_hearings_days,
        NOW()
    FROM per_court p
    ON CONFLICT (court_id)
    DO UPDATE SET
        mean_adjournment_rate = EXCLUDED.mean_adjournment_rate,
        std_dev_adjournment_rate = EXCLUDED.std_dev_adjournment_rate,
        median_time_between_hearings_days = EXCLUDED.median_time_between_hearings_days,
        calculated_at = NOW()
    RETURNING court_id
    """
)


@celery_app.task(name="app.tasks.analytics.compute_court_analytical_snapshots")
def compute_court_analytical_snapshots() -> dict[str, Any]:
    """Batch-compute per-court analytical baselines and upsert snapshot rows."""
    db = SessionLocal()
    try:
        with db.begin():
            db.execute(text("SET LOCAL TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            result = db.execute(AGGREGATION_UPSERT_SQL)
            affected_court_ids = [int(row[0]) for row in result.fetchall()]

        logger.info(
            "Computed court analytical snapshots",
            extra={"updated_courts": len(affected_court_ids)},
        )
        return {
            "status": "success",
            "updated_courts": len(affected_court_ids),
            "court_ids": affected_court_ids,
        }
    except Exception:
        db.rollback()
        logger.exception("Failed to compute court analytical snapshots")
        raise
    finally:
        db.close()
