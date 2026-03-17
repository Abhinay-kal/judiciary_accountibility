from __future__ import annotations


def compute_baseline_confidence(
    *,
    sample_size: int,
    recency_days: float,
    median_delay: float,
    iqr_delay: float,
    fallback_depth: int,
) -> float:
    sample_component = min(1.0, sample_size / 150.0)
    recency_component = max(0.2, 1.0 - (recency_days / 3650.0))

    if median_delay <= 0:
        spread_component = 0.4
    else:
        relative_spread = iqr_delay / max(1.0, median_delay)
        spread_component = max(0.2, 1.0 - min(1.0, relative_spread))

    fallback_penalty = max(0.5, 1.0 - (0.08 * max(0, fallback_depth)))

    confidence = (
        0.45 * sample_component
        + 0.25 * recency_component
        + 0.30 * spread_component
    ) * fallback_penalty
    return max(0.0, min(1.0, round(confidence, 4)))
