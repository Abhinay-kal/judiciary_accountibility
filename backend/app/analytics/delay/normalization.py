from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.analytics.delay.confidence import compute_baseline_confidence
from app.analytics.delay.metrics import DelayMetrics
from app.models import Case, DelayBaseline

BASELINE_ORDER = [
    "court_case_type",
    "court",
    "state_case_type",
    "state",
    "national_case_type",
    "national",
]


@dataclass
class BaselineChoice:
    baseline: DelayBaseline | None
    fallback_depth: int


def _lookup_key(level: str, case: Case) -> tuple[str, int | None, str | None, str | None]:
    case_type = (case.case_type or "unknown").strip().lower() or "unknown"
    if level == "court_case_type":
        return (level, case.court_id, None, case_type)
    if level == "court":
        return (level, case.court_id, None, None)
    if level == "state_case_type":
        return (level, None, case.state, case_type)
    if level == "state":
        return (level, None, case.state, None)
    if level == "national_case_type":
        return (level, None, None, case_type)
    return ("national", None, None, None)


def choose_baseline(
    case: Case,
    baseline_index: dict[tuple[str, int | None, str | None, str | None], DelayBaseline],
    *,
    min_sample_size: int,
) -> BaselineChoice:
    fallback_candidate: DelayBaseline | None = None
    fallback_depth = len(BASELINE_ORDER)

    for depth, level in enumerate(BASELINE_ORDER):
        baseline = baseline_index.get(_lookup_key(level, case))
        if baseline is None:
            continue
        if fallback_candidate is None:
            fallback_candidate = baseline
            fallback_depth = depth
        if baseline.sample_size >= min_sample_size:
            return BaselineChoice(baseline=baseline, fallback_depth=depth)

    return BaselineChoice(baseline=fallback_candidate, fallback_depth=fallback_depth)


def _approx_percentile(delay: float, baseline: DelayBaseline) -> float:
    median = max(1.0, baseline.median_delay)
    p75 = max(median, baseline.p75_delay)
    p90 = max(p75, baseline.p90_delay)

    if delay <= median:
        return max(0.0, min(50.0, (delay / median) * 50.0))
    if delay <= p75:
        span = max(1.0, p75 - median)
        return 50.0 + ((delay - median) / span) * 25.0
    if delay <= p90:
        span = max(1.0, p90 - p75)
        return 75.0 + ((delay - p75) / span) * 15.0

    tail = (delay - p90) / max(1.0, p90 - median)
    return min(99.9, 90.0 + (tail * 10.0))


def _severity(
    normalized_delay: float,
    percentile: float,
    robust_z: float,
    *,
    moderate_threshold: float,
    high_threshold: float,
    extreme_threshold: float,
) -> str:
    if normalized_delay >= extreme_threshold or percentile >= 99.0 or robust_z >= 3.0:
        return "EXTREME_DELAY"
    if normalized_delay >= high_threshold or percentile >= 95.0 or robust_z >= 2.0:
        return "HIGH_DELAY"
    if normalized_delay >= moderate_threshold or percentile >= 90.0:
        return "MODERATE_DELAY"
    return "NORMAL"


def normalize_case_delay(
    *,
    case: Case,
    case_delay_days: float | None,
    baseline_index: dict[tuple[str, int | None, str | None, str | None], DelayBaseline],
    min_sample_size: int = 20,
    moderate_threshold: float = 1.5,
    high_threshold: float = 2.0,
    extreme_threshold: float = 3.0,
) -> tuple[DelayMetrics | None, BaselineChoice, float]:
    choice = choose_baseline(case, baseline_index, min_sample_size=min_sample_size)
    baseline = choice.baseline
    if case_delay_days is None or baseline is None:
        return None, choice, 0.0

    median = max(1.0, baseline.median_delay)
    iqr = max(1.0, baseline.iqr_delay)

    normalized_delay = float(case_delay_days) / median
    percentile = _approx_percentile(float(case_delay_days), baseline)
    robust_z = (float(case_delay_days) - median) / iqr
    severity = _severity(
        normalized_delay,
        percentile,
        robust_z,
        moderate_threshold=moderate_threshold,
        high_threshold=high_threshold,
        extreme_threshold=extreme_threshold,
    )

    computed_at = baseline.computed_at
    if computed_at.tzinfo is None:
        computed_at = computed_at.replace(tzinfo=timezone.utc)
    recency_days = max(0.0, (datetime.now(timezone.utc) - computed_at).total_seconds() / 86400.0)

    confidence = compute_baseline_confidence(
        sample_size=baseline.sample_size,
        recency_days=recency_days,
        median_delay=baseline.median_delay,
        iqr_delay=baseline.iqr_delay,
        fallback_depth=choice.fallback_depth,
    )

    return (
        DelayMetrics(
            delay_days=float(case_delay_days),
            normalized_delay=round(normalized_delay, 4),
            delay_percentile=round(percentile, 2),
            robust_z_score=round(robust_z, 4),
            delay_severity=severity,
        ),
        choice,
        confidence,
    )
