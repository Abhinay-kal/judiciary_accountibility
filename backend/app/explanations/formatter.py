from __future__ import annotations


def format_days_as_human(days: float | None) -> str:
    if days is None:
        return "an unknown duration"
    if days < 0:
        days = 0.0
    years = int(days // 365)
    months = int((days % 365) // 30)
    if years <= 0:
        return f"{months} months"
    if months <= 0:
        return f"{years} years"
    return f"{years} years {months} months"


def round_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)


def round_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 0)
