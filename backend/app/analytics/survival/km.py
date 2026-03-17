from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class KaplanMeierResult:
    time_points: list[float]
    survival: list[float]
    lower_ci: list[float]
    upper_ci: list[float]
    median_time: float | None
    q75_disposal_time: float | None
    event_count: int
    sample_size: int


def _greenwood_ci(survival: np.ndarray, var_sum: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    z = 1.96
    se = np.sqrt(np.maximum(0.0, (survival ** 2) * var_sum))
    lower = np.clip(survival - (z * se), 0.0, 1.0)
    upper = np.clip(survival + (z * se), 0.0, 1.0)
    return lower, upper


def fit_kaplan_meier(durations: np.ndarray, events: np.ndarray) -> KaplanMeierResult:
    if durations.size == 0:
        return KaplanMeierResult([], [], [], [], None, None, 0, 0)

    durations = durations.astype(float)
    events = events.astype(int)

    order = np.argsort(durations, kind="mergesort")
    d_sorted = durations[order]
    e_sorted = events[order]

    unique_times = np.unique(d_sorted)
    n = len(d_sorted)

    survival_vals = []
    var_components = []
    at_risk = float(n)
    cumulative_survival = 1.0
    var_sum = 0.0

    for t in unique_times:
        mask = d_sorted == t
        d_i = float(np.sum(e_sorted[mask] == 1))
        c_i = float(np.sum(e_sorted[mask] == 0))

        if d_i > 0 and at_risk > 0:
            cumulative_survival *= (1.0 - (d_i / at_risk))
            if (at_risk - d_i) > 0:
                var_sum += d_i / (at_risk * (at_risk - d_i))

        survival_vals.append(cumulative_survival)
        var_components.append(var_sum)
        at_risk -= (d_i + c_i)

    surv_arr = np.array(survival_vals, dtype=float)
    var_arr = np.array(var_components, dtype=float)
    lower, upper = _greenwood_ci(surv_arr, var_arr)

    median_time = None
    q75_disposal_time = None
    for t, s in zip(unique_times, surv_arr):
        if median_time is None and s <= 0.5:
            median_time = float(t)
        if q75_disposal_time is None and s <= 0.25:
            q75_disposal_time = float(t)

    return KaplanMeierResult(
        time_points=[float(value) for value in unique_times.tolist()],
        survival=[float(value) for value in surv_arr.tolist()],
        lower_ci=[float(value) for value in lower.tolist()],
        upper_ci=[float(value) for value in upper.tolist()],
        median_time=median_time,
        q75_disposal_time=q75_disposal_time,
        event_count=int(np.sum(events == 1)),
        sample_size=int(n),
    )


def survival_at_time(result: KaplanMeierResult, day: float) -> float:
    if not result.time_points:
        return 1.0
    value = 1.0
    for t, s in zip(result.time_points, result.survival):
        if day < t:
            break
        value = s
    return float(value)
