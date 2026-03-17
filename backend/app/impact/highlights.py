from __future__ import annotations

from app.impact.comparators import ComparatorBundle
from app.impact.templates import T_HEADLINE_FALLBACK, T_HEADLINE_PERCENTILE, T_HEADLINE_RATIO, T_QUOTE_PERCENTILE, T_QUOTE_RATIO, get_template


def build_headline(*, case_type: str, comparators: ComparatorBundle, locale: str = "en") -> str:
    case_type_title = (case_type or "Case").title()
    if comparators.ratio is not None and comparators.duration_years is not None and comparators.ratio >= 1.2:
        return get_template(T_HEADLINE_RATIO, locale).format(
            case_type_title=case_type_title,
            duration_years=comparators.duration_years,
            ratio=comparators.ratio,
        )
    if comparators.percentile is not None and comparators.percentile >= 70:
        return get_template(T_HEADLINE_PERCENTILE, locale).format(
            case_type_title=case_type_title,
            percentile=comparators.percentile,
        )
    return get_template(T_HEADLINE_FALLBACK, locale)


def build_key_takeaways(*, comparators: ComparatorBundle, anomaly_flags: list[str], status_phrase: str) -> list[str]:
    rows: list[str] = [f"Current status: {status_phrase}."]
    if comparators.ratio is not None:
        rows.append(f"Relative duration is about {comparators.ratio:.1f}x versus similar cases.")
    if comparators.percentile is not None:
        rows.append(f"This case is in the slower {max(0, 100 - comparators.percentile):.0f}% segment of comparable cases.")
    if comparators.survival_percent is not None:
        rows.append(f"Estimated unresolved share at current age: {comparators.survival_percent:.1f}%.")
    if anomaly_flags:
        rows.append(f"Active pattern flags: {', '.join(flag.replace('_', ' ') for flag in anomaly_flags[:3])}.")
    return rows[:5]


def build_shareable_quote(*, comparators: ComparatorBundle, locale: str = "en") -> str:
    if comparators.percentile is not None and comparators.percentile >= 70:
        return get_template(T_QUOTE_PERCENTILE, locale).format(percentile=comparators.percentile)
    if comparators.ratio is not None:
        return get_template(T_QUOTE_RATIO, locale).format(ratio=comparators.ratio)
    return "This case timeline appears longer than typical, based on available data."
