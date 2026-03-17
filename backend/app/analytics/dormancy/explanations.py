from __future__ import annotations

from dataclasses import dataclass

from app.analytics.dormancy.baseline import BaselineSelection
from app.analytics.dormancy.features import DormancyFeatures
from app.analytics.dormancy.rules import DormancyRuleResult
from app.analytics.dormancy.scoring import DormancyScoreResult


@dataclass
class DormancyExplanation:
    summary: str
    details: dict


def generate_dormancy_explanation(
    *,
    features: DormancyFeatures,
    baseline: BaselineSelection,
    rules: DormancyRuleResult,
    score: DormancyScoreResult,
) -> DormancyExplanation:
    if rules.excluded:
        summary = "Dormancy screening skipped due to exclusion criteria."
        details = {
            "exclusion_reason": rules.exclusion_reason,
            "data_confidence": features.data_confidence,
            "future_listing_exists": features.future_listing_exists,
            "stay_status": features.stay_status,
        }
        return DormancyExplanation(summary=summary, details=details)

    if rules.absolute_days is None or rules.normalized_inactivity is None:
        summary = "Dormancy score unavailable due to incomplete baseline evidence."
        details = {
            "data_confidence": features.data_confidence,
            "baseline_level": baseline.level,
        }
        return DormancyExplanation(summary=summary, details=details)

    percentile_like = max(1, min(99, int(min(99.0, rules.normalized_inactivity / 6.0 * 100.0))))
    years_silent = round(float(rules.absolute_days) / 365.0, 1)

    summary = (
        f"This case has had no substantive hearings for {years_silent} years, "
        f"longer than approximately {percentile_like}% of similar cases in this context."
    )

    details = {
        "severity": score.severity,
        "dormancy_score": score.score,
        "normalized_inactivity": rules.normalized_inactivity,
        "absolute_inactivity_days": rules.absolute_days,
        "baseline_level": baseline.level,
        "baseline_median_gap_days": baseline.baseline.median_gap_days if baseline.baseline else None,
        "baseline_sample_size": baseline.baseline.sample_size if baseline.baseline else None,
        "future_listing_exists": features.future_listing_exists,
        "trend_worsening": features.trend_worsening,
        "timeline_marker": (
            f"Case entered dormant state on {features.last_activity_date.isoformat()}"
            if score.status == "dormant" and features.last_activity_date is not None
            else None
        ),
        "defamation_safe_note": "Dormancy indicates procedural inactivity signals only; it is not an allegation of misconduct.",
    }

    return DormancyExplanation(summary=summary, details=details)
