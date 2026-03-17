from __future__ import annotations

from datetime import datetime, timezone

import numpy as np


def time_weighted_median(values: list[float], timestamps: list[datetime], half_life_days: int = 730) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    now = datetime.now(timezone.utc)
    weighted = []
    for value, ts in zip(values, timestamps):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
        decay = 0.5 ** (age_days / max(1.0, float(half_life_days)))
        weighted.append((float(value), float(decay)))

    weighted.sort(key=lambda item: item[0])
    total_w = sum(weight for _, weight in weighted)
    if total_w <= 0:
        return float(np.median(values))

    cumulative = 0.0
    for value, weight in weighted:
        cumulative += weight
        if cumulative >= total_w / 2.0:
            return float(value)
    return float(weighted[-1][0])
