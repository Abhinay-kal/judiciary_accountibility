from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComparatorBundle:
    ratio: float | None
    percentile: float | None
    duration_years: float | None
    survival_percent: float | None


def build_comparators(
    *,
    normalized_delay: float | None,
    delay_percentile: float | None,
    duration_days: float | None,
    survival_probability: float | None,
    baseline_median_days: float | None,
) -> ComparatorBundle:
    ratio = normalized_delay
    if ratio is None and duration_days is not None and baseline_median_days and baseline_median_days > 0:
        ratio = duration_days / baseline_median_days

    duration_years = None if duration_days is None else round(duration_days / 365.0, 2)
    survival_percent = None if survival_probability is None else round(100.0 * survival_probability, 1)

    return ComparatorBundle(
        ratio=round(ratio, 2) if ratio is not None else None,
        percentile=round(delay_percentile, 1) if delay_percentile is not None else None,
        duration_years=duration_years,
        survival_percent=survival_percent,
    )
