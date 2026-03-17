from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from app.analytics.survival.dataset import SurvivalRow, to_numpy_arrays
from app.analytics.survival.hazard import hazard_from_km
from app.analytics.survival.km import KaplanMeierResult, fit_kaplan_meier


@dataclass
class StratifiedCurve:
    grouping_type: str
    grouping_value: str
    case_type: str | None
    km: KaplanMeierResult
    hazard: list[float]


def _key(row: SurvivalRow, grouping_type: str, include_case_type: bool) -> tuple[str, str | None]:
    if grouping_type == "court":
        primary = str(row.court_id) if row.court_id is not None else "unknown"
    elif grouping_type == "state":
        primary = row.state or "unknown"
    elif grouping_type == "case_type":
        primary = row.case_type or "unknown"
    elif grouping_type == "judge":
        primary = str(row.judge_id) if row.judge_id is not None else "unknown"
    else:
        primary = "all"

    if include_case_type:
        return primary, row.case_type or "unknown"
    return primary, None


def compute_stratified_curves(
    rows: list[SurvivalRow],
    *,
    grouping_type: str,
    include_case_type: bool = False,
    min_sample_size: int = 25,
) -> list[StratifiedCurve]:
    buckets: dict[tuple[str, str | None], list[SurvivalRow]] = defaultdict(list)
    for row in rows:
        buckets[_key(row, grouping_type, include_case_type)].append(row)

    curves: list[StratifiedCurve] = []
    for (group_value, case_type), bucket in buckets.items():
        if len(bucket) < min_sample_size:
            continue
        durations, events = to_numpy_arrays(bucket)
        km = fit_kaplan_meier(durations, events)
        hz = hazard_from_km(km, durations, events, window=7)
        curves.append(
            StratifiedCurve(
                grouping_type=grouping_type,
                grouping_value=group_value,
                case_type=case_type,
                km=km,
                hazard=hz,
            )
        )

    return curves
