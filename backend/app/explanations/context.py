from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Case, DelayBaseline, Flag, SurvivalCurve


@dataclass
class ExplanationContext:
    case_id: int
    case_type: str
    court_level: str
    state: str
    is_pending: bool
    duration_days: float | None
    normalized_delay: float | None
    percentile: float | None
    survival_probability: float | None
    strategic_delay_score: float | None
    importance_score: float | None
    baseline_median_days: float | None
    anomaly_flags: list[str]
    baseline_confidence: float | None
    importance_confidence: float | None


def build_explanation_context(db: Session, case: Case) -> ExplanationContext:
    case_type = case.case_type or "comparable"
    duration_days = float(case.case_duration_days) if case.case_duration_days is not None else _duration_from_dates(case)

    baseline = _select_baseline(db, case)
    survival_probability = _survival_at_case_age(db, case, duration_days or 0.0)

    flags = (
        db.query(Flag)
        .filter(Flag.case_id == case.id, Flag.is_deleted.is_(False), Flag.is_active.is_(True))
        .order_by(Flag.score.desc().nullslast())
        .all()
    )

    return ExplanationContext(
        case_id=case.id,
        case_type=case_type,
        court_level=case.court_level or "court",
        state=case.state,
        is_pending=not bool(case.is_disposed),
        duration_days=duration_days,
        normalized_delay=float(case.normalized_delay) if case.normalized_delay is not None else None,
        percentile=float(case.delay_percentile) if case.delay_percentile is not None else None,
        survival_probability=survival_probability,
        strategic_delay_score=float(case.importance_score) if case.importance_score is not None else None,
        importance_score=float(case.importance_score) if case.importance_score is not None else None,
        baseline_median_days=float(baseline.median_delay) if baseline else None,
        anomaly_flags=[row.flag_type for row in flags],
        baseline_confidence=float(case.baseline_confidence) if case.baseline_confidence is not None else None,
        importance_confidence=float(case.importance_confidence) if case.importance_confidence is not None else None,
    )


def _duration_from_dates(case: Case) -> float | None:
    if case.filing_date is None:
        return None
    end_date = date.today()
    if case.is_disposed and case.last_source_updated_at is not None:
        end_date = case.last_source_updated_at.date()
    return float(max(0, (end_date - case.filing_date).days))


def _select_baseline(db: Session, case: Case) -> DelayBaseline | None:
    rows = (
        db.query(DelayBaseline)
        .filter(DelayBaseline.state == case.state)
        .order_by(DelayBaseline.computed_at.desc())
        .all()
    )
    for item in rows:
        if item.case_type == case.case_type and item.baseline_level == (case.baseline_level_used or item.baseline_level):
            return item
    return rows[0] if rows else None


def _survival_at_case_age(db: Session, case: Case, age_days: float) -> float | None:
    case_type = (case.case_type or "unknown").strip().lower() or "unknown"
    candidates = [
        ("court_case_type", str(case.court_id), case_type),
        ("court", str(case.court_id), None),
        ("state_case_type", case.state or "unknown", case_type),
        ("state", case.state or "unknown", None),
        ("national", "all", case_type),
        ("national", "all", None),
    ]
    selected = None
    for grouping_type, grouping_value, ctype in candidates:
        selected = (
            db.query(SurvivalCurve)
            .filter(
                SurvivalCurve.grouping_type == grouping_type,
                SurvivalCurve.grouping_value == grouping_value,
                SurvivalCurve.case_type == ctype,
            )
            .one_or_none()
        )
        if selected is not None:
            break
    if selected is None:
        return None

    value = 1.0
    for day, prob in zip(selected.time_points or [], selected.survival_probabilities or []):
        if float(age_days) < float(day):
            break
        value = float(prob)
    return max(0.0, min(1.0, value))
