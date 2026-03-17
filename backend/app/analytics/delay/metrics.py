from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DelayMetrics:
    delay_days: float
    normalized_delay: float | None
    delay_percentile: float | None
    robust_z_score: float | None
    delay_severity: str


def build_delay_summary_text(
    *,
    normalized_delay: float | None,
    delay_percentile: float | None,
    baseline_label: str | None,
) -> str | None:
    if normalized_delay is None or delay_percentile is None:
        return None
    label_map = {
        "court_case_type": "similar cases in this court",
        "court": "cases in this court",
        "state_case_type": "similar cases in this state",
        "state": "cases in this state",
        "national_case_type": "similar cases nationwide",
        "national": "cases nationwide",
    }
    label = label_map.get(baseline_label or "", "comparable cases")
    return (
        f"This case has lasted {normalized_delay:.1f}x longer than {label} "
        f"({delay_percentile:.0f}th percentile)."
    )
