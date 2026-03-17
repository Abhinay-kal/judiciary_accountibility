from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.analytics.dormancy.baseline import BaselineSelection, DormancyBaseline
from app.analytics.dormancy.explanations import generate_dormancy_explanation
from app.analytics.dormancy.features import DormancyFeatures
from app.analytics.dormancy.rules import DormancyThresholds, evaluate_dormancy_rules
from app.analytics.dormancy.scoring import compute_dormancy_score
from app.api.routes import cases
from app.main import app


def _features(**overrides) -> DormancyFeatures:
    base = DormancyFeatures(
        case_id=1,
        status="pending",
        is_disposed=False,
        state="Delhi",
        case_type="civil",
        case_stage="arguments",
        court_id=10,
        days_since_last_hearing=900,
        days_since_last_order=720,
        days_since_last_listing=900,
        case_age_days=1500,
        number_of_hearings=8,
        adjournment_count=6,
        bail_status=None,
        stay_status=None,
        future_listing_exists=False,
        days_since_last_activity=900,
        last_activity_date=date.today() - timedelta(days=900),
        trend_worsening=True,
        recent_transfer=False,
        data_confidence=0.9,
    )
    payload = {**base.__dict__, **overrides}
    return DormancyFeatures(**payload)


def test_truly_dormant_case_flagged() -> None:
    features = _features()
    baseline = BaselineSelection(
        baseline=DormancyBaseline(
            key=("court_case_type", 10, "civil", None),
            median_gap_days=180.0,
            sample_size=120,
        ),
        level="court_case_type",
        confidence=0.9,
    )
    normalized = (features.days_since_last_hearing or 0) / baseline.baseline.median_gap_days
    rules = evaluate_dormancy_rules(features, baseline, normalized, DormancyThresholds())
    assert rules.is_candidate is True

    score = compute_dormancy_score(features, rules, normalized_inactivity=normalized, case_importance=0.8)
    assert score.status == "dormant"
    assert score.score >= 0.45


def test_normal_case_not_flagged() -> None:
    features = _features(days_since_last_hearing=45, days_since_last_activity=45, trend_worsening=False, adjournment_count=0)
    baseline = BaselineSelection(
        baseline=DormancyBaseline(
            key=("court_case_type", 10, "civil", None),
            median_gap_days=60.0,
            sample_size=120,
        ),
        level="court_case_type",
        confidence=0.9,
    )
    normalized = (features.days_since_last_hearing or 0) / baseline.baseline.median_gap_days
    rules = evaluate_dormancy_rules(features, baseline, normalized, DormancyThresholds())
    assert rules.is_candidate is False

    score = compute_dormancy_score(features, rules, normalized_inactivity=normalized, case_importance=0.2)
    assert score.status == "active_watch"


def test_recently_reactivated_case_downgraded() -> None:
    features = _features(
        days_since_last_hearing=7,
        days_since_last_listing=7,
        days_since_last_activity=3,
        future_listing_exists=True,
        trend_worsening=False,
    )
    baseline = BaselineSelection(
        baseline=DormancyBaseline(
            key=("court_case_type", 10, "civil", None),
            median_gap_days=120.0,
            sample_size=80,
        ),
        level="court_case_type",
        confidence=0.8,
    )
    normalized = (features.days_since_last_hearing or 0) / baseline.baseline.median_gap_days
    rules = evaluate_dormancy_rules(features, baseline, normalized, DormancyThresholds())
    assert rules.excluded is True
    assert rules.exclusion_reason == "future_hearing_scheduled"


def test_missing_data_low_confidence_excluded() -> None:
    features = _features(
        days_since_last_hearing=None,
        days_since_last_order=None,
        days_since_last_listing=None,
        days_since_last_activity=None,
        number_of_hearings=0,
        data_confidence=0.2,
    )
    baseline = BaselineSelection(baseline=None, level="none", confidence=0.0)
    rules = evaluate_dormancy_rules(features, baseline, None, DormancyThresholds())
    assert rules.excluded is True
    assert rules.exclusion_reason == "low_data_confidence"


def test_edge_case_active_stay_not_flagged() -> None:
    features = _features(stay_status="active")
    baseline = BaselineSelection(
        baseline=DormancyBaseline(
            key=("court_case_type", 10, "civil", None),
            median_gap_days=90.0,
            sample_size=100,
        ),
        level="court_case_type",
        confidence=0.9,
    )
    normalized = (features.days_since_last_hearing or 0) / baseline.baseline.median_gap_days
    rules = evaluate_dormancy_rules(features, baseline, normalized, DormancyThresholds())
    assert rules.excluded is True
    assert rules.exclusion_reason == "active_stay_order"


def test_explanation_text_contains_context() -> None:
    features = _features()
    baseline = BaselineSelection(
        baseline=DormancyBaseline(
            key=("court_case_type", 10, "civil", None),
            median_gap_days=180.0,
            sample_size=120,
        ),
        level="court_case_type",
        confidence=0.9,
    )
    normalized = (features.days_since_last_hearing or 0) / baseline.baseline.median_gap_days
    rules = evaluate_dormancy_rules(features, baseline, normalized, DormancyThresholds())
    score = compute_dormancy_score(features, rules, normalized_inactivity=normalized, case_importance=0.8)
    explanation = generate_dormancy_explanation(features=features, baseline=baseline, rules=rules, score=score)

    assert "no substantive hearings" in explanation.summary.lower()
    assert explanation.details["timeline_marker"] is not None


@dataclass
class _CaseStub:
    id: int
    is_deleted: bool = False


class _FakeQuery:
    def __init__(self, rows: list[_CaseStub]):
        self._rows = rows
        self._offset = 0
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def count(self):
        return len(self._rows)

    def offset(self, value: int):
        self._offset = value
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def all(self):
        rows = self._rows[self._offset :]
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self):
        self.rows = [_CaseStub(1), _CaseStub(2)]

    def query(self, model):
        _ = model
        return _FakeQuery(self.rows)


def _override_get_db():
    yield _FakeSession()


def test_dormancy_api_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(cases, "_serialize_case", lambda case, db: {"id": case.id, "dormancy_status": "mild_dormancy", "dormancy_score": 0.6})
    monkeypatch.setattr(
        cases,
        "_compute_case_dormancy",
        lambda case, db: {
            "case_id": case.id,
            "status": "dormant",
            "severity": "mild_dormancy",
            "dormancy_score": 0.6,
            "explanation": "Dormant case",
            "timeline_marker": "Case entered dormant state on 2025-01-01",
        },
    )

    app.dependency_overrides[cases.get_db] = _override_get_db
    client = TestClient(app)

    resp_list = client.get("/api/v1/cases/dormant")
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] == 2

    resp_one = client.get("/api/v1/cases/1/dormancy")
    assert resp_one.status_code == 200
    assert resp_one.json()["status"] == "dormant"

    app.dependency_overrides.clear()
