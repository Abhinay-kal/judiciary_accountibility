from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json
from app.models import SurvivalCurve


def get_curve_snapshot(db: Session, *, grouping_type: str, grouping_value: str, case_type: str | None = None) -> dict | None:
    cache_key = f"{grouping_type}|{grouping_value}|{case_type}"

    def _producer() -> dict | None:
        row = (
            db.query(SurvivalCurve)
            .filter(
                SurvivalCurve.grouping_type == grouping_type,
                SurvivalCurve.grouping_value == grouping_value,
                SurvivalCurve.case_type == case_type,
            )
            .one_or_none()
        )
        if row is None:
            return None
        return {
            "curve_id": row.curve_id,
            "grouping_type": row.grouping_type,
            "grouping_value": row.grouping_value,
            "case_type": row.case_type,
            "time_points": row.time_points,
            "survival_probabilities": row.survival_probabilities,
            "lower_ci": row.lower_ci,
            "upper_ci": row.upper_ci,
            "hazard_rates": row.hazard_rates,
            "median_time": row.median_time,
            "sample_size": row.sample_size,
            "event_count": row.event_count,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }

    return get_or_set_json("survival_curves", cache_key, _producer, ttl_seconds=3600)
