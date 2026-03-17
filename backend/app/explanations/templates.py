from __future__ import annotations

T_DELAY_RATIO_HIGH = "DELAY_RATIO_HIGH"
T_DELAY_RATIO_MODERATE = "DELAY_RATIO_MODERATE"
T_PERCENTILE_HIGH = "PERCENTILE_HIGH"
T_PERCENTILE_MODERATE = "PERCENTILE_MODERATE"
T_SURVIVAL_PROBABILITY = "SURVIVAL_PROBABILITY"
T_PENDING_CONTEXT = "PENDING_CONTEXT"
T_DISPOSED_CONTEXT = "DISPOSED_CONTEXT"
T_PATTERN_FLAG = "PATTERN_FLAG"
T_IMPORTANCE_HIGH = "IMPORTANCE_HIGH"
T_IMPORTANCE_MODERATE = "IMPORTANCE_MODERATE"
T_LOW_CONFIDENCE_NOTE = "LOW_CONFIDENCE_NOTE"
T_FALLBACK_INSUFFICIENT = "FALLBACK_INSUFFICIENT"
T_NON_ACCUSATORY = "NON_ACCUSATORY"

DEFAULT_TEMPLATES_EN: dict[str, str] = {
    T_DELAY_RATIO_HIGH: "This case has been pending {ratio:.1f}x longer than similar {case_type} cases in this court.",
    T_DELAY_RATIO_MODERATE: "This case duration is above typical levels for similar {case_type} cases in this court.",
    T_PERCENTILE_HIGH: "This case is slower than {percentile:.0f}% of comparable cases.",
    T_PERCENTILE_MODERATE: "This case is slower than average among comparable cases.",
    T_SURVIVAL_PROBABILITY: "Only {survival_percent:.0f}% of similar cases remain unresolved after {years:.1f} years.",
    T_PENDING_CONTEXT: "The case has been pending for {duration_human}.",
    T_DISPOSED_CONTEXT: "The case took {duration_human} to resolve.",
    T_PATTERN_FLAG: "Pattern observed: {flag_label}.",
    T_IMPORTANCE_HIGH: "This case has a high public-interest importance score based on objective signals.",
    T_IMPORTANCE_MODERATE: "This case has a moderate public-interest importance score based on objective signals.",
    T_LOW_CONFIDENCE_NOTE: "Based on limited available data, these findings should be interpreted with caution.",
    T_FALLBACK_INSUFFICIENT: "Not enough comparable cases are currently available to assess delay reliably.",
    T_NON_ACCUSATORY: "These findings describe case-level timeline patterns and do not by themselves establish misconduct.",
}
