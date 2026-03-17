from __future__ import annotations

from dataclasses import dataclass

from app.analytics.dormancy.features import DormancyFeatures
from app.analytics.dormancy.rules import DormancyRuleResult


@dataclass
class DormancyScoreResult:
    score: float
    status: str
    severity: str
    confidence: float


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_dormancy_score(
    features: DormancyFeatures,
    rule_result: DormancyRuleResult,
    *,
    normalized_inactivity: float | None,
    case_importance: float | None,
) -> DormancyScoreResult:
    if rule_result.excluded:
        return DormancyScoreResult(score=0.0, status="excluded", severity="none", confidence=max(0.1, features.data_confidence))

    if normalized_inactivity is None or rule_result.absolute_days is None:
        return DormancyScoreResult(score=0.0, status="unknown", severity="none", confidence=features.data_confidence)

    rel_component = _clamp(normalized_inactivity / 6.0)
    abs_component = _clamp(float(rule_result.absolute_days) / float(365 * 5))
    importance_component = _clamp(case_importance or 0.0)

    pattern_bonus = 0.0
    if features.trend_worsening:
        pattern_bonus += 0.08
    if features.adjournment_count >= 5:
        pattern_bonus += 0.06

    if not rule_result.is_candidate:
        base = 0.2 * rel_component + 0.2 * abs_component + 0.1 * importance_component
        return DormancyScoreResult(
            score=round(_clamp(base), 4),
            status="active_watch",
            severity="none",
            confidence=round(max(0.2, features.data_confidence), 3),
        )

    weighted = 0.45 * rel_component + 0.35 * abs_component + 0.15 * importance_component + pattern_bonus
    weighted = _clamp(weighted)

    confidence = _clamp(0.4 + 0.4 * features.data_confidence + (0.2 if features.number_of_hearings >= 2 else 0.0))

    return DormancyScoreResult(
        score=round(weighted, 4),
        status="dormant",
        severity=rule_result.severity,
        confidence=round(confidence, 3),
    )


def should_keep_flag(score: float, is_candidate: bool) -> bool:
    if is_candidate:
        return score >= 0.45
    return score >= 0.8
