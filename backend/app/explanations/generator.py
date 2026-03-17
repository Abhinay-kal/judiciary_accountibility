from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.explanations.confidence import confidence_note, summary_confidence_score
from app.explanations.context import ExplanationContext, build_explanation_context
from app.explanations.formatter import format_days_as_human, round_percent, round_ratio
from app.explanations.localization import get_template
from app.explanations.templates import (
    T_DELAY_RATIO_HIGH,
    T_DELAY_RATIO_MODERATE,
    T_DISPOSED_CONTEXT,
    T_FALLBACK_INSUFFICIENT,
    T_IMPORTANCE_HIGH,
    T_IMPORTANCE_MODERATE,
    T_LOW_CONFIDENCE_NOTE,
    T_NON_ACCUSATORY,
    T_PATTERN_FLAG,
    T_PENDING_CONTEXT,
    T_PERCENTILE_HIGH,
    T_PERCENTILE_MODERATE,
    T_SURVIVAL_PROBABILITY,
)
from app.models import Case


@dataclass
class ExplanationResult:
    short_summary: str
    detailed_summary: str
    bullet_points: list[str]
    confidence_note: str | None
    key_metrics_used: list[str]
    summary_confidence: float

    def to_dict(self) -> dict:
        return {
            "short_summary": self.short_summary,
            "detailed_summary": self.detailed_summary,
            "bullet_points": self.bullet_points,
            "confidence_note": self.confidence_note,
            "key_metrics_used": self.key_metrics_used,
            "summary_confidence": self.summary_confidence,
        }


def generate_explanation(ctx: ExplanationContext, locale: str = "en") -> ExplanationResult:
    bullets: list[str] = []
    metrics_used: list[str] = []

    duration_human = format_days_as_human(ctx.duration_days)
    context_tpl = T_PENDING_CONTEXT if ctx.is_pending else T_DISPOSED_CONTEXT
    bullets.append(get_template(context_tpl, locale).format(duration_human=duration_human))
    if ctx.duration_days is not None:
        metrics_used.append("duration_days")

    ratio = _derive_delay_ratio(ctx)
    if ratio is not None and ratio >= 2.0:
        bullets.append(get_template(T_DELAY_RATIO_HIGH, locale).format(ratio=round_ratio(ratio), case_type=ctx.case_type))
        metrics_used.append("normalized_delay")
    elif ratio is not None and ratio >= 1.2:
        bullets.append(get_template(T_DELAY_RATIO_MODERATE, locale).format(case_type=ctx.case_type))
        metrics_used.append("normalized_delay")

    percentile = round_percent(ctx.percentile)
    if percentile is not None and percentile >= 90:
        bullets.append(get_template(T_PERCENTILE_HIGH, locale).format(percentile=percentile))
        metrics_used.append("percentile")
    elif percentile is not None and percentile >= 70:
        bullets.append(get_template(T_PERCENTILE_MODERATE, locale))
        metrics_used.append("percentile")

    if ctx.survival_probability is not None and ctx.duration_days is not None:
        bullets.append(
            get_template(T_SURVIVAL_PROBABILITY, locale).format(
                survival_percent=round(100.0 * ctx.survival_probability, 1),
                years=round(ctx.duration_days / 365.0, 1),
            )
        )
        metrics_used.append("survival_probability")

    if ctx.importance_score is not None:
        if ctx.importance_score >= 0.75:
            bullets.append(get_template(T_IMPORTANCE_HIGH, locale))
        elif ctx.importance_score >= 0.45:
            bullets.append(get_template(T_IMPORTANCE_MODERATE, locale))
        metrics_used.append("importance_score")

    for flag in ctx.anomaly_flags[:2]:
        bullets.append(get_template(T_PATTERN_FLAG, locale).format(flag_label=flag.replace("_", " ")))
        metrics_used.append("anomaly_flags")

    if not metrics_used:
        fallback = get_template(T_FALLBACK_INSUFFICIENT, locale)
        bullets = [fallback]
        short_summary = fallback
        detailed = fallback
        score = 0.2
        note = get_template(T_LOW_CONFIDENCE_NOTE, locale)
        return ExplanationResult(
            short_summary=short_summary,
            detailed_summary=detailed,
            bullet_points=bullets,
            confidence_note=note,
            key_metrics_used=[],
            summary_confidence=score,
        )

    score = summary_confidence_score(ctx)
    note = confidence_note(score)
    if note:
        bullets.append(get_template(T_LOW_CONFIDENCE_NOTE, locale))

    bullets.append(get_template(T_NON_ACCUSATORY, locale))
    short_summary = bullets[0]
    detailed = " ".join(bullets[:4])

    return ExplanationResult(
        short_summary=short_summary,
        detailed_summary=detailed,
        bullet_points=bullets,
        confidence_note=note,
        key_metrics_used=sorted(set(metrics_used)),
        summary_confidence=score,
    )


def generate_case_summary(db: Session, case: Case, locale: str = "en") -> ExplanationResult:
    ctx = build_explanation_context(db, case)
    return generate_explanation(ctx, locale=locale)


def generate_and_store_case_summary(db: Session, case: Case, locale: str = "en") -> ExplanationResult:
    result = generate_case_summary(db, case, locale=locale)
    case.plain_summary_short = result.short_summary
    case.plain_summary_detailed = result.detailed_summary
    case.summary_confidence = result.summary_confidence
    case.last_summary_update = datetime.now(timezone.utc)
    return result


def _derive_delay_ratio(ctx: ExplanationContext) -> float | None:
    if ctx.normalized_delay is not None:
        return float(ctx.normalized_delay)
    if ctx.duration_days is not None and ctx.baseline_median_days:
        if ctx.baseline_median_days <= 0:
            return None
        return float(ctx.duration_days) / float(ctx.baseline_median_days)
    return None
