from __future__ import annotations

from datetime import datetime


def build_credibility_notes(
    *,
    confidence: float,
    updated_at: datetime | None,
    low_data: bool,
    sources: list[str],
) -> dict:
    return {
        "confidence_score": round(confidence, 3),
        "last_updated": updated_at.isoformat() if updated_at is not None else None,
        "data_sources": sources,
        "methodology_reference": "See delay normalization, percentile benchmarking, and survival analytics modules.",
        "uncertainty": "Limited comparator coverage." if low_data else "Comparator coverage is sufficient for directional interpretation.",
    }
