from __future__ import annotations

from dataclasses import dataclass

from app.analytics.dormancy.baseline import BaselineSelection
from app.analytics.dormancy.features import DormancyFeatures


@dataclass
class DormancyThresholds:
    min_days_default: int = 180
    min_days_by_case_type: dict[str, int] | None = None
    normalized_threshold: float = 2.0
    severe_normalized_threshold: float = 3.0

    def min_days_for(self, case_type: str | None) -> int:
        if not self.min_days_by_case_type:
            return self.min_days_default
        key = (case_type or "unknown").strip().lower() or "unknown"
        return int(self.min_days_by_case_type.get(key, self.min_days_default))


@dataclass
class DormancyRuleResult:
    is_candidate: bool
    excluded: bool
    exclusion_reason: str | None
    absolute_days: int | None
    normalized_inactivity: float | None
    severity: str


def _is_pending(status: str) -> bool:
    text = (status or "").strip().lower()
    return text in {"pending", "active", "in_progress"}


def _severity(days: int, norm: float) -> str:
    if days >= 365 * 5 or norm >= 6.0:
        return "extreme_inactivity"
    if days >= 365 * 3 or norm >= 4.5:
        return "severe_dormancy"
    if days >= 365 or norm >= 3.0:
        return "significant_dormancy"
    return "mild_dormancy"


def evaluate_dormancy_rules(
    features: DormancyFeatures,
    selected: BaselineSelection,
    normalized: float | None,
    thresholds: DormancyThresholds,
    *,
    future_listing_exclusion_days: int = 30,
    min_data_confidence: float = 0.5,
) -> DormancyRuleResult:
    absolute_days = features.days_since_last_hearing or features.days_since_last_activity

    if features.is_disposed or not _is_pending(features.status):
        return DormancyRuleResult(False, True, "case_not_pending", absolute_days, normalized, "none")

    if features.stay_status in {"active", "in_force", "granted"}:
        return DormancyRuleResult(False, True, "active_stay_order", absolute_days, normalized, "none")

    if features.future_listing_exists and (features.days_since_last_listing or 0) <= future_listing_exclusion_days:
        return DormancyRuleResult(False, True, "future_hearing_scheduled", absolute_days, normalized, "none")

    if features.recent_transfer:
        return DormancyRuleResult(False, True, "recent_court_transfer", absolute_days, normalized, "none")

    if features.data_confidence < min_data_confidence:
        return DormancyRuleResult(False, True, "low_data_confidence", absolute_days, normalized, "none")

    if absolute_days is None or normalized is None or selected.baseline is None:
        return DormancyRuleResult(False, True, "insufficient_baseline_data", absolute_days, normalized, "none")

    min_days = thresholds.min_days_for(features.case_type)
    meets = (
        not features.future_listing_exists
        and normalized >= thresholds.normalized_threshold
        and absolute_days >= min_days
    )

    if not meets:
        return DormancyRuleResult(False, False, None, absolute_days, normalized, "none")

    return DormancyRuleResult(True, False, None, absolute_days, normalized, _severity(absolute_days, normalized))
