from __future__ import annotations

import numpy as np

from app.analytics.survival.km import KaplanMeierResult


def discrete_hazard(time_points: list[float], durations: np.ndarray, events: np.ndarray) -> np.ndarray:
    hazards = []
    if len(time_points) == 0:
        return np.array([], dtype=float)

    for t in time_points:
        at_risk = float(np.sum(durations >= t))
        if at_risk <= 0:
            hazards.append(0.0)
            continue
        event_count = float(np.sum((durations == t) & (events == 1)))
        hazards.append(event_count / at_risk)
    return np.array(hazards, dtype=float)


def smooth_hazard(hazard_values: np.ndarray, window: int = 5) -> np.ndarray:
    if hazard_values.size == 0:
        return hazard_values
    w = max(1, int(window))
    if w == 1:
        return hazard_values
    kernel = np.ones(w, dtype=float) / float(w)
    return np.convolve(hazard_values, kernel, mode="same")


def hazard_from_km(result: KaplanMeierResult, durations: np.ndarray, events: np.ndarray, window: int = 5) -> list[float]:
    raw = discrete_hazard(result.time_points, durations, events)
    smooth = smooth_hazard(raw, window=window)
    return [float(value) for value in smooth.tolist()]
