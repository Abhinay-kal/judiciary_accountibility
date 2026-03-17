from __future__ import annotations

from app.explanations.context import ExplanationContext
from app.explanations.formatter import format_days_as_human, round_percent, round_ratio
from app.explanations.generator import generate_explanation
from app.explanations.localization import get_template
from app.explanations.templates import T_FALLBACK_INSUFFICIENT


def _ctx(**overrides) -> ExplanationContext:
    base = ExplanationContext(
        case_id=1,
        case_type="criminal",
        court_level="district",
        state="Delhi",
        is_pending=True,
        duration_days=3400.0,
        normalized_delay=3.2,
        percentile=93.0,
        survival_probability=0.18,
        strategic_delay_score=0.8,
        importance_score=0.78,
        baseline_median_days=1060.0,
        anomaly_flags=["strategic_delay_pattern"],
        baseline_confidence=0.8,
        importance_confidence=0.82,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_numeric_formatting_helpers():
    assert format_days_as_human(10) == "0 months"
    assert format_days_as_human(365) == "1 years"
    assert format_days_as_human(760) == "2 years 1 months"
    assert round_ratio(3.26) == 3.3
    assert round_percent(92.7) == 93.0


def test_template_selection_high_delay_and_percentile():
    result = generate_explanation(_ctx())
    assert "3.2x longer" in result.detailed_summary
    assert "slower than 93%" in result.detailed_summary
    assert "normalized_delay" in result.key_metrics_used
    assert "percentile" in result.key_metrics_used


def test_low_confidence_note_is_added():
    result = generate_explanation(_ctx(baseline_confidence=0.2, importance_confidence=0.2, percentile=None, normalized_delay=None))
    assert result.confidence_note is not None
    assert "limited available data" in result.confidence_note


def test_fallback_when_insufficient_data():
    result = generate_explanation(
        _ctx(
            duration_days=None,
            normalized_delay=None,
            percentile=None,
            survival_probability=None,
            importance_score=None,
            anomaly_flags=[],
            baseline_confidence=None,
            importance_confidence=None,
        )
    )
    assert result.short_summary == get_template(T_FALLBACK_INSUFFICIENT)
    assert result.key_metrics_used == []


def test_localization_readiness_fallback_to_english_template():
    template = get_template("DELAY_RATIO_HIGH", locale="hi")
    assert "This case has been pending" in template
