from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from app.analytics.dormancy.features import DormancyFeatures


@dataclass
class DormancyBaseline:
    key: tuple[str, str | int | None, str | None, str | None]
    median_gap_days: float
    sample_size: int


@dataclass
class BaselineSelection:
    baseline: DormancyBaseline | None
    level: str
    confidence: float


_LEVELS = (
    "court_case_type_stage",
    "court_case_type",
    "court",
    "state_case_type",
    "state",
    "national_case_type",
    "national",
)


def _safe_case_type(value: str | None) -> str:
    return (value or "unknown").strip().lower() or "unknown"


def _safe_stage(value: str | None) -> str:
    return (value or "unknown").strip().lower() or "unknown"


def baseline_key(level: str, features: DormancyFeatures) -> tuple[str, str | int | None, str | None, str | None]:
    case_type = _safe_case_type(features.case_type)
    stage = _safe_stage(features.case_stage)
    if level == "court_case_type_stage":
        return (level, features.court_id, case_type, stage)
    if level == "court_case_type":
        return (level, features.court_id, case_type, None)
    if level == "court":
        return (level, features.court_id, None, None)
    if level == "state_case_type":
        return (level, features.state, case_type, None)
    if level == "state":
        return (level, features.state, None, None)
    if level == "national_case_type":
        return (level, "all", case_type, None)
    return ("national", "all", None, None)


def compute_baselines(feature_rows: Iterable[DormancyFeatures], *, min_samples: int = 20) -> dict[tuple[str, str | int | None, str | None, str | None], DormancyBaseline]:
    grouped: dict[tuple[str, str | int | None, str | None, str | None], list[int]] = {}

    for row in feature_rows:
        inactivity = row.days_since_last_hearing
        if inactivity is None:
            continue
        if row.number_of_hearings < 2:
            continue
        for level in _LEVELS:
            key = baseline_key(level, row)
            grouped.setdefault(key, []).append(inactivity)

    result: dict[tuple[str, str | int | None, str | None, str | None], DormancyBaseline] = {}
    for key, values in grouped.items():
        if len(values) < min_samples:
            continue
        median_gap = max(1.0, float(median(values)))
        result[key] = DormancyBaseline(key=key, median_gap_days=median_gap, sample_size=len(values))

    return result


def select_baseline(
    features: DormancyFeatures,
    baseline_index: dict[tuple[str, str | int | None, str | None, str | None], DormancyBaseline],
    *,
    min_samples: int = 20,
) -> BaselineSelection:
    for depth, level in enumerate(_LEVELS):
        key = baseline_key(level, features)
        baseline = baseline_index.get(key)
        if baseline is None:
            continue
        if baseline.sample_size >= min_samples:
            confidence = max(0.15, min(1.0, baseline.sample_size / float(min_samples * 5)))
            return BaselineSelection(baseline=baseline, level=level, confidence=round(confidence, 3))

    fallback = baseline_index.get(("national", "all", None, None))
    if fallback is None:
        return BaselineSelection(baseline=None, level="none", confidence=0.0)

    confidence = max(0.1, min(0.6, fallback.sample_size / float(min_samples * 10)))
    return BaselineSelection(baseline=fallback, level="national", confidence=round(confidence, 3))


def normalized_inactivity(features: DormancyFeatures, selected: BaselineSelection) -> float | None:
    if selected.baseline is None:
        return None
    days = features.days_since_last_hearing
    if days is None:
        return None
    return round(float(days) / max(1.0, selected.baseline.median_gap_days), 4)
