from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.analytics.delay.baselines import (
    BASELINE_COURT,
    BASELINE_COURT_CASE_TYPE,
    BASELINE_NATIONAL,
    compute_case_delay_days,
)
from app.analytics.delay.normalization import choose_baseline, normalize_case_delay
from app.models import DelayBaseline


def _baseline(*, level: str, court_id=None, state=None, case_type=None, median=100.0, p75=150.0, p90=220.0, iqr=50.0, sample=50):
    return DelayBaseline(
        baseline_level=level,
        court_id=court_id,
        state=state,
        case_type=case_type,
        median_delay=median,
        p75_delay=p75,
        p90_delay=p90,
        iqr_delay=iqr,
        sample_size=sample,
        window_years=7,
        computed_at=datetime.now(timezone.utc),
    )


def test_small_sample_falls_back_to_next_level():
    case = SimpleNamespace(court_id=1, state="Delhi", case_type="Criminal")
    primary = _baseline(level=BASELINE_COURT_CASE_TYPE, court_id=1, case_type="criminal", sample=4)
    fallback = _baseline(level=BASELINE_COURT, court_id=1, sample=120)
    index = {
        (primary.baseline_level, primary.court_id, primary.state, primary.case_type): primary,
        (fallback.baseline_level, fallback.court_id, fallback.state, fallback.case_type): fallback,
    }

    picked = choose_baseline(case, index, min_sample_size=20)

    assert picked.baseline is not None
    assert picked.baseline.baseline_level == BASELINE_COURT
    assert picked.fallback_depth == 1


def test_extreme_outlier_marked_extreme_delay():
    case = SimpleNamespace(court_id=1, state="Delhi", case_type="Criminal")
    baseline = _baseline(level=BASELINE_COURT_CASE_TYPE, court_id=1, case_type="criminal", median=100, p75=140, p90=180, iqr=40)
    index = {(baseline.baseline_level, baseline.court_id, baseline.state, baseline.case_type): baseline}

    metrics, choice, confidence = normalize_case_delay(
        case=case,
        case_delay_days=420,
        baseline_index=index,
        min_sample_size=20,
    )

    assert metrics is not None
    assert metrics.delay_severity == "EXTREME_DELAY"
    assert metrics.normalized_delay is not None and metrics.normalized_delay > 3.0
    assert confidence > 0


def test_missing_case_type_uses_unknown_bucket():
    case = SimpleNamespace(court_id=1, state="Delhi", case_type=None)
    baseline = _baseline(level=BASELINE_COURT_CASE_TYPE, court_id=1, case_type="unknown", median=200)
    index = {(baseline.baseline_level, baseline.court_id, baseline.state, baseline.case_type): baseline}

    metrics, _, _ = normalize_case_delay(case=case, case_delay_days=200, baseline_index=index, min_sample_size=1)

    assert metrics is not None
    assert metrics.normalized_delay == 1.0


def test_compute_case_delay_for_disposed_and_active():
    disposed = SimpleNamespace(
        filing_date=date(2020, 1, 1),
        status="disposed",
        source_fields={"disposal_date": "2021-01-01"},
        updated_at=datetime(2021, 1, 3, tzinfo=timezone.utc),
    )
    active = SimpleNamespace(
        filing_date=date(2020, 1, 1),
        status="pending",
        source_fields={},
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    disposed_delay = compute_case_delay_days(disposed, now=date(2026, 1, 1))
    active_delay = compute_case_delay_days(active, now=date(2026, 1, 1))

    assert disposed_delay == 366.0
    assert active_delay == float((date(2026, 1, 1) - date(2020, 1, 1)).days)


def test_fallback_reaches_national_when_others_missing():
    case = SimpleNamespace(court_id=1, state="Delhi", case_type="Tax")
    national = _baseline(level=BASELINE_NATIONAL, median=240, p75=320, p90=450, iqr=120, sample=600)
    index = {(national.baseline_level, national.court_id, national.state, national.case_type): national}

    metrics, choice, _ = normalize_case_delay(case=case, case_delay_days=300, baseline_index=index, min_sample_size=20)

    assert metrics is not None
    assert choice.baseline is not None
    assert choice.baseline.baseline_level == BASELINE_NATIONAL
