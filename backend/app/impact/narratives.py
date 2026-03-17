from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.explanations.context import build_explanation_context
from app.explanations.formatter import format_days_as_human
from app.impact.audience import adapt_executive_summary, normalize_audience, policymaker_note
from app.impact.calls_to_action import build_calls_to_action
from app.impact.comparators import build_comparators
from app.impact.credibility import build_credibility_notes
from app.impact.framing import build_impact_statement, build_why_it_matters
from app.impact.highlights import build_headline, build_key_takeaways, build_shareable_quote
from app.impact.templates import T_EXEC_SUMMARY, T_EXEC_SUMMARY_LOW_DATA, get_template
from app.models import Case


@dataclass
class ImpactOutput:
    headline: str
    executive_summary: str
    key_takeaways: list[str]
    why_it_matters: str
    impact_statement: str
    calls_to_action: list[str]
    journalist_quote: str
    policymaker_note: str
    credibility_notes: dict
    impact_confidence: float

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "executive_summary": self.executive_summary,
            "key_takeaways": self.key_takeaways,
            "why_it_matters": self.why_it_matters,
            "impact_statement": self.impact_statement,
            "calls_to_action": self.calls_to_action,
            "journalist_quote": self.journalist_quote,
            "policymaker_note": self.policymaker_note,
            "credibility_notes": self.credibility_notes,
            "impact_confidence": self.impact_confidence,
        }


def generate_case_impact(
    db: Session,
    case: Case,
    *,
    audience: str = "general_public",
    locale: str = "en",
) -> ImpactOutput:
    ctx = build_explanation_context(db, case)
    audience_slug = normalize_audience(audience)

    comparators = build_comparators(
        normalized_delay=ctx.normalized_delay,
        delay_percentile=ctx.percentile,
        duration_days=ctx.duration_days,
        survival_probability=ctx.survival_probability,
        baseline_median_days=ctx.baseline_median_days,
    )
    duration_human = format_days_as_human(ctx.duration_days)
    status_phrase = "been pending" if ctx.is_pending else "been resolved"

    low_data = comparators.ratio is None and comparators.percentile is None and comparators.survival_percent is None

    headline = build_headline(case_type=ctx.case_type, comparators=comparators, locale=locale)
    if low_data:
        summary = get_template(T_EXEC_SUMMARY_LOW_DATA, locale).format(
            case_type=ctx.case_type,
            status_phrase=status_phrase,
            duration_human=duration_human,
        )
    else:
        summary = get_template(T_EXEC_SUMMARY, locale).format(
            case_type=ctx.case_type,
            status_phrase=status_phrase,
            duration_human=duration_human,
        )
        if comparators.ratio is not None:
            summary += f" The current duration is approximately {comparators.ratio:.1f}x the comparable median."
        elif comparators.percentile is not None:
            summary += f" It is slower than about {comparators.percentile:.0f}% of comparable cases."

    executive = adapt_executive_summary(audience=audience_slug, base_summary=summary)
    takeaways = build_key_takeaways(
        comparators=comparators,
        anomaly_flags=ctx.anomaly_flags,
        status_phrase=status_phrase,
    )

    confidence_components = [item for item in [ctx.baseline_confidence, ctx.importance_confidence] if item is not None]
    impact_confidence = round((sum(confidence_components) / len(confidence_components)), 3) if confidence_components else 0.35

    credibility = build_credibility_notes(
        confidence=impact_confidence,
        updated_at=case.impact_last_updated,
        low_data=low_data,
        sources=[case.source_url] if case.source_url else [],
    )

    return ImpactOutput(
        headline=headline,
        executive_summary=executive,
        key_takeaways=takeaways,
        why_it_matters=build_why_it_matters(case_type=ctx.case_type, is_pending=ctx.is_pending, percentile=comparators.percentile),
        impact_statement=build_impact_statement(strategic_delay_score=ctx.strategic_delay_score, importance_score=ctx.importance_score),
        calls_to_action=build_calls_to_action(audience=audience_slug, is_pending=ctx.is_pending),
        journalist_quote=build_shareable_quote(comparators=comparators, locale=locale),
        policymaker_note=policymaker_note(),
        credibility_notes=credibility,
        impact_confidence=impact_confidence,
    )


def generate_and_store_case_impact(
    db: Session,
    case: Case,
    *,
    audience: str = "general_public",
    locale: str = "en",
) -> ImpactOutput:
    result = generate_case_impact(db, case, audience=audience, locale=locale)
    case.impact_headline = result.headline
    case.impact_summary = result.executive_summary
    case.impact_confidence = result.impact_confidence
    case.impact_last_updated = datetime.now(timezone.utc)
    return result
