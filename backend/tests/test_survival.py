from __future__ import annotations

from datetime import date

import numpy as np

from app.analytics.survival.dataset import SurvivalRow, compute_duration_and_event
from app.analytics.survival.km import fit_kaplan_meier, survival_at_time
from app.analytics.survival.prediction import case_survival_prediction, expected_remaining_days
from app.analytics.survival.stratified import compute_stratified_curves
from app.models import Case


def _case(*, filing_date: date, status: str, source_fields: dict | None = None) -> Case:
    return Case(
        case_uid="uid-1",
        case_number="case-1",
        court_id=1,
        court_level="district",
        state="Delhi",
        status=status,
        source_url="https://example.com",
        filing_date=filing_date,
        source_fields=source_fields or {},
    )


def test_compute_duration_and_event_for_disposed_case_uses_disposal_date() -> None:
    now = date(2026, 1, 1)
    case = _case(
        filing_date=date(2025, 1, 1),
        status="disposed",
        source_fields={"disposal_date": "2025-07-01"},
    )

    duration, event = compute_duration_and_event(case, now=now)

    assert event == 1
    assert duration == float((date(2025, 7, 1) - date(2025, 1, 1)).days)


def test_compute_duration_and_event_for_pending_case_is_right_censored() -> None:
    now = date(2026, 1, 1)
    case = _case(filing_date=date(2025, 1, 1), status="pending")

    duration, event = compute_duration_and_event(case, now=now)

    assert event == 0
    assert duration == float((now - date(2025, 1, 1)).days)


def test_kaplan_meier_median_and_ci_bounds() -> None:
    durations = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
    events = np.array([1, 1, 0, 1], dtype=int)

    result = fit_kaplan_meier(durations, events)

    assert result.sample_size == 4
    assert result.event_count == 3
    assert result.median_time == 2.0
    assert len(result.time_points) == len(result.survival) == len(result.lower_ci) == len(result.upper_ci)
    for lo, s, hi in zip(result.lower_ci, result.survival, result.upper_ci):
        assert 0.0 <= lo <= s <= hi <= 1.0


def test_survival_at_time_is_step_function() -> None:
    durations = np.array([10.0, 20.0], dtype=float)
    events = np.array([1, 1], dtype=int)
    result = fit_kaplan_meier(durations, events)

    assert survival_at_time(result, 0.0) == 1.0
    assert survival_at_time(result, 10.0) == 0.5
    assert survival_at_time(result, 15.0) == 0.5
    assert survival_at_time(result, 20.0) == 0.0


def test_compute_stratified_curves_respects_min_sample_size() -> None:
    rows = [
        SurvivalRow(1, 100.0, 1, 1, "Delhi", "civil", 11),
        SurvivalRow(2, 200.0, 0, 1, "Delhi", "civil", 11),
        SurvivalRow(3, 150.0, 1, 2, "Karnataka", "civil", 12),
    ]

    curves = compute_stratified_curves(
        rows,
        grouping_type="court",
        include_case_type=False,
        min_sample_size=2,
    )

    assert len(curves) == 1
    assert curves[0].grouping_value == "1"
    assert curves[0].km.sample_size == 2


def test_case_survival_prediction_flags_unusual_delay() -> None:
    durations = np.array([100.0, 200.0, 300.0, 400.0], dtype=float)
    events = np.array([1, 1, 1, 1], dtype=int)
    km = fit_kaplan_meier(durations, events)

    prediction = case_survival_prediction(
        curve=km,
        case_age_days=350.0,
        additional_days=365.0,
        percentile_threshold=70.0,
    )

    assert 0.0 <= prediction.survival_at_case_age <= 1.0
    assert 0.0 <= prediction.survival_after_additional_days <= prediction.survival_at_case_age
    assert prediction.percentile_rank >= 70.0
    assert prediction.unusual_delay is True


def test_expected_remaining_days_non_negative() -> None:
    durations = np.array([100.0, 200.0, 300.0], dtype=float)
    events = np.array([1, 1, 1], dtype=int)
    km = fit_kaplan_meier(durations, events)

    remaining = expected_remaining_days(km, case_age_days=150.0)

    assert remaining is not None
    assert remaining >= 0.0
