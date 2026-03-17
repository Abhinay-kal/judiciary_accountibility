from __future__ import annotations

from dataclasses import dataclass

from app.analytics.survival.km import KaplanMeierResult, survival_at_time


@dataclass
class SurvivalCasePrediction:
    survival_at_case_age: float
    survival_after_additional_days: float
    median_expected_duration_days: float | None
    percentile_rank: float
    unusual_delay: bool


def expected_remaining_days(result: KaplanMeierResult, case_age_days: float) -> float | None:
    if not result.time_points:
        return None

    # Approximate expected remaining time by discrete area under survival tail.
    area = 0.0
    prev_t = case_age_days
    prev_s = survival_at_time(result, case_age_days)

    for t, s in zip(result.time_points, result.survival):
        if t <= case_age_days:
            continue
        dt = t - prev_t
        area += dt * ((prev_s + s) / 2.0)
        prev_t = t
        prev_s = s

    return max(0.0, float(area))


def case_survival_prediction(
    *,
    curve: KaplanMeierResult,
    case_age_days: float,
    additional_days: float,
    percentile_threshold: float = 90.0,
) -> SurvivalCasePrediction:
    s_age = survival_at_time(curve, case_age_days)
    s_future = survival_at_time(curve, case_age_days + additional_days)

    percentile = (1.0 - s_age) * 100.0
    unusual = percentile >= percentile_threshold

    return SurvivalCasePrediction(
        survival_at_case_age=round(s_age, 4),
        survival_after_additional_days=round(s_future, 4),
        median_expected_duration_days=curve.median_time,
        percentile_rank=round(percentile, 2),
        unusual_delay=bool(unusual),
    )
