from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.explanations.context import ExplanationContext
from app.impact.narratives import generate_case_impact


def _ctx(**overrides) -> ExplanationContext:
    base = ExplanationContext(
        case_id=9,
        case_type="corruption",
        court_level="district",
        state="Delhi",
        is_pending=True,
        duration_days=3200.0,
        normalized_delay=3.0,
        percentile=92.0,
        survival_probability=0.24,
        strategic_delay_score=0.81,
        importance_score=0.7,
        baseline_median_days=1050.0,
        anomaly_flags=["baseline_delay_anomaly"],
        baseline_confidence=0.84,
        importance_confidence=0.78,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _case() -> SimpleNamespace:
    return SimpleNamespace(
        id=9,
        source_url="https://example.org/source/9",
        impact_last_updated=datetime(2026, 3, 17, tzinfo=timezone.utc),
    )


def test_headline_contains_relative_metric(monkeypatch):
    monkeypatch.setattr("app.impact.narratives.build_explanation_context", lambda db, case: _ctx())
    output = generate_case_impact(None, _case())
    assert "3.0x longer" in output.headline
    assert "comparable median" in output.executive_summary


def test_no_accusatory_language(monkeypatch):
    monkeypatch.setattr("app.impact.narratives.build_explanation_context", lambda db, case: _ctx())
    output = generate_case_impact(None, _case())
    combined = " ".join(
        [
            output.headline,
            output.executive_summary,
            output.why_it_matters,
            output.impact_statement,
            output.journalist_quote,
            output.policymaker_note,
        ]
        + output.key_takeaways
        + output.calls_to_action
    ).lower()
    banned = ["guilty", "intentional wrongdoing", "criminal intent", "cover-up", "conspiracy", "harass"]
    assert not any(token in combined for token in banned)


def test_low_data_uses_preliminary_language(monkeypatch):
    monkeypatch.setattr(
        "app.impact.narratives.build_explanation_context",
        lambda db, case: _ctx(
            normalized_delay=None,
            percentile=None,
            survival_probability=None,
            baseline_median_days=None,
        ),
    )
    output = generate_case_impact(None, _case())
    assert "preliminary" in output.executive_summary.lower()
    assert output.credibility_notes["uncertainty"] == "Limited comparator coverage."


def test_audience_adaptation_changes_summary(monkeypatch):
    monkeypatch.setattr("app.impact.narratives.build_explanation_context", lambda db, case: _ctx())
    case = _case()
    journalist = generate_case_impact(None, case, audience="journalists")
    policymaker = generate_case_impact(None, case, audience="policymakers")
    assert "public-interest reporting" in journalist.executive_summary
    assert "administrative and process-efficiency review" in policymaker.executive_summary


def test_structured_output_shape(monkeypatch):
    monkeypatch.setattr("app.impact.narratives.build_explanation_context", lambda db, case: _ctx())
    output = generate_case_impact(None, _case()).to_dict()
    expected_keys = {
        "headline",
        "executive_summary",
        "key_takeaways",
        "why_it_matters",
        "impact_statement",
        "calls_to_action",
        "journalist_quote",
        "policymaker_note",
        "credibility_notes",
        "impact_confidence",
    }
    assert set(output.keys()) == expected_keys
