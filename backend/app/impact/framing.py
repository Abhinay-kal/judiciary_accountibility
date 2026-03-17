from __future__ import annotations


def build_why_it_matters(*, case_type: str, is_pending: bool, percentile: float | None) -> str:
    if is_pending:
        base = "Extended pending durations can reduce predictability for litigants and institutions."
    else:
        base = "Long resolution times can increase legal uncertainty and administrative burden."

    if percentile is not None and percentile >= 90:
        return base + " This case is among the slower comparable matters, making it relevant for accountability and process review."
    return base + " Timely tracking helps identify where process improvements may be needed."


def build_impact_statement(*, strategic_delay_score: float | None, importance_score: float | None) -> str:
    if strategic_delay_score is not None and strategic_delay_score >= 0.75:
        return "Extended delays can weaken deterrence, increase legal uncertainty, and reduce trust in procedural efficiency."
    if importance_score is not None and importance_score >= 0.6:
        return "Because this is a higher-importance case, timeline delays may have broader public-accountability implications."
    return "Sustained delays in any case can affect predictability, resource use, and confidence in justice delivery."
