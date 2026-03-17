from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Case


def warmup_top_case_ids(db: Session, limit: int = 100) -> list[int]:
    rows = (
        db.query(Case.id)
        .filter(Case.is_deleted.is_(False))
        .order_by(Case.importance_score.desc().nullslast(), Case.case_duration_days.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [int(row[0]) for row in rows]


def refresh_precomputed_tables(db: Session) -> dict:
    """Refresh heavy stats tables (L3 persistent cache)."""

    now = datetime.now(timezone.utc)

    db.execute(text("DELETE FROM court_stats"))
    db.execute(
        text(
            """
            INSERT INTO court_stats (court_id, total_cases, pending_cases, disposed_cases, backlog_ratio, computed_at)
            SELECT
                c.court_id,
                COUNT(*) AS total_cases,
                SUM(CASE WHEN COALESCE(c.is_disposed, false) = false THEN 1 ELSE 0 END) AS pending_cases,
                SUM(CASE WHEN COALESCE(c.is_disposed, false) = true THEN 1 ELSE 0 END) AS disposed_cases,
                CASE WHEN COUNT(*) = 0 THEN 0.0 ELSE
                    (SUM(CASE WHEN COALESCE(c.is_disposed, false) = false THEN 1 ELSE 0 END)::float / COUNT(*)::float)
                END AS backlog_ratio,
                :computed_at
            FROM cases c
            WHERE c.is_deleted = false
            GROUP BY c.court_id
            """
        ),
        {"computed_at": now},
    )

    db.execute(text("DELETE FROM state_metrics"))
    db.execute(
        text(
            """
            INSERT INTO state_metrics (state, total_cases, pending_cases, avg_normalized_delay, computed_at)
            SELECT
                c.state,
                COUNT(*) AS total_cases,
                SUM(CASE WHEN COALESCE(c.is_disposed, false) = false THEN 1 ELSE 0 END) AS pending_cases,
                AVG(COALESCE(c.normalized_delay, 0.0)) AS avg_normalized_delay,
                :computed_at
            FROM cases c
            WHERE c.is_deleted = false
            GROUP BY c.state
            """
        ),
        {"computed_at": now},
    )

    db.execute(text("DELETE FROM case_type_metrics"))
    db.execute(
        text(
            """
            INSERT INTO case_type_metrics (case_type, total_cases, pending_cases, avg_delay_percentile, computed_at)
            SELECT
                COALESCE(c.case_type, 'unknown') AS case_type,
                COUNT(*) AS total_cases,
                SUM(CASE WHEN COALESCE(c.is_disposed, false) = false THEN 1 ELSE 0 END) AS pending_cases,
                AVG(COALESCE(c.delay_percentile, 0.0)) AS avg_delay_percentile,
                :computed_at
            FROM cases c
            WHERE c.is_deleted = false
            GROUP BY COALESCE(c.case_type, 'unknown')
            """
        ),
        {"computed_at": now},
    )

    db.execute(text("DELETE FROM judge_stats"))
    db.execute(
        text(
            """
            INSERT INTO judge_stats (judge_id, hearing_count, avg_outcome_confidence, computed_at)
            SELECT
                h.judge_id,
                COUNT(*) AS hearing_count,
                AVG(COALESCE(h.outcome_confidence, 0.0)) AS avg_outcome_confidence,
                :computed_at
            FROM hearings h
            WHERE h.is_deleted = false AND h.judge_id IS NOT NULL
            GROUP BY h.judge_id
            """
        ),
        {"computed_at": now},
    )

    db.commit()
    return {"refreshed_at": now.isoformat()}
