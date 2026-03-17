from __future__ import annotations

from app.explanations.context import ExplanationContext


def summary_confidence_score(ctx: ExplanationContext) -> float:
    components = []
    if ctx.baseline_confidence is not None:
        components.append(ctx.baseline_confidence)
    if ctx.importance_confidence is not None:
        components.append(ctx.importance_confidence)
    if ctx.percentile is not None:
        components.append(0.8)
    if ctx.normalized_delay is not None:
        components.append(0.8)
    if ctx.survival_probability is not None:
        components.append(0.7)
    if not components:
        return 0.2
    return round(sum(components) / len(components), 3)


def confidence_note(score: float, low_threshold: float = 0.5) -> str | None:
    if score < low_threshold:
        return "Based on limited available data, these findings should be interpreted with caution."
    return None
