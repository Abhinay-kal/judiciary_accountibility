from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SurvivalCurve

router = APIRouter(prefix="/survival", tags=["survival"])


@router.get("/curve")
def get_survival_curve(
    grouping_type: str = Query(...),
    grouping_value: str = Query(...),
    case_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
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
        raise HTTPException(status_code=404, detail="Survival curve not found")

    one_year = 365.0
    two_year = 2 * 365.0
    five_year = 5 * 365.0
    ten_year = 10 * 365.0

    def _survival_at(day: float) -> float:
        value = 1.0
        for t, s in zip(row.time_points or [], row.survival_probabilities or []):
            if day < float(t):
                break
            value = float(s)
        return value

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
        "survival_at_1y": _survival_at(one_year),
        "survival_at_2y": _survival_at(two_year),
        "survival_at_5y": _survival_at(five_year),
        "survival_at_10y": _survival_at(ten_year),
        "cumulative_incidence_at_10y": round(1.0 - _survival_at(ten_year), 4),
        "summary": (
            f"Only {(100.0 * _survival_at(ten_year)):.1f}% of similar cases remain pending after 10 years."
        ),
    }
