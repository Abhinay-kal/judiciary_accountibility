from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.analytics.delay.baselines import build_and_store_delay_baselines


class _QueryStub:
    def __init__(self, cases):
        self.cases = cases

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.cases)

    def delete(self):
        return None


class _DBStub:
    def __init__(self, cases):
        self.cases = cases
        self.inserted = []

    def query(self, _model):
        return _QueryStub(self.cases)

    def add(self, row):
        self.inserted.append(row)

    def commit(self):
        return None


def test_baseline_builder_aggregates_multiple_levels():
    now = datetime.now(timezone.utc)
    cases = [
        SimpleNamespace(
            filing_date=date.today() - timedelta(days=200),
            status="pending",
            source_fields={},
            updated_at=now,
            last_source_updated_at=now,
            case_type="Criminal",
            court_id=1,
            state="Delhi",
            is_deleted=False,
        ),
        SimpleNamespace(
            filing_date=date.today() - timedelta(days=500),
            status="pending",
            source_fields={},
            updated_at=now,
            last_source_updated_at=now,
            case_type="Criminal",
            court_id=1,
            state="Delhi",
            is_deleted=False,
        ),
    ]

    db = _DBStub(cases)
    summary = build_and_store_delay_baselines(db, window_years=7)

    assert summary["cases_considered"] == 2
    assert summary["baselines_written"] >= 3
    assert any(item.baseline_level == "court_case_type" for item in db.inserted)


def test_old_cases_outside_window_are_ignored():
    now = datetime.now(timezone.utc)
    recent_case = SimpleNamespace(
        filing_date=date.today() - timedelta(days=100),
        status="pending",
        source_fields={},
        updated_at=now,
        last_source_updated_at=now,
        case_type="Civil",
        court_id=1,
        state="Delhi",
        is_deleted=False,
    )
    old_case = SimpleNamespace(
        filing_date=date.today() - timedelta(days=4000),
        status="pending",
        source_fields={},
        updated_at=now,
        last_source_updated_at=now,
        case_type="Civil",
        court_id=1,
        state="Delhi",
        is_deleted=False,
    )

    db = _DBStub([recent_case, old_case])
    summary = build_and_store_delay_baselines(db, window_years=3)

    assert summary["cases_considered"] == 1
    assert summary["baselines_written"] >= 1
