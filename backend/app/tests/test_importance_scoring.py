from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import Case
from app.services.importance import CaseImportanceScorer


class _QueryStub:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows

    def one_or_none(self):
        return None

    def count(self):
        return len(self._rows)


class _DBStub:
    def __init__(self, rows=None):
        self._rows = rows or []

    def query(self, *args, **kwargs):
        return _QueryStub(self._rows)

    def add(self, *args, **kwargs):
        return None

    def flush(self):
        return None


def _make_case() -> Case:
    return Case(
        case_uid="CASE-1",
        case_number="1/2025",
        court_id=1,
        court_level="high",
        state="Delhi",
        status="pending",
        source_url="https://example.org/case/1",
        source_fields={},
        importance_override={"score": 0.88, "reason": "manual"},
    )


def test_importance_override_is_applied(monkeypatch):
    db = _DBStub()
    scorer = CaseImportanceScorer(db)
    case = _make_case()

    monkeypatch.setattr(
        scorer,
        "_resolve_config",
        lambda: {
            "weights": CaseImportanceScorer.DEFAULT_WEIGHTS,
            "case_type_map": CaseImportanceScorer.DEFAULT_CASE_TYPE_MAP,
            "min_confidence": 0.2,
            "media_decay_lambda": 0.05,
            "monetary_cap": 50000000.0,
        },
    )
    monkeypatch.setattr(scorer, "_politician_flag_score", lambda *_: (0.0, {}))
    monkeypatch.setattr(scorer, "_corruption_text_score", lambda *_: (0.0, {}))
    monkeypatch.setattr(scorer, "_case_type_score", lambda *_: 0.0)
    monkeypatch.setattr(scorer, "_monetary_value_score", lambda *_: (0.0, {}))
    monkeypatch.setattr(scorer, "_judicial_priority_score", lambda *_: 0.0)
    monkeypatch.setattr(scorer, "_historical_public_interest_score", lambda *_: (0.0, {}))
    monkeypatch.setattr(scorer, "_media_mentions_score", lambda *_: (0.0, {"used": False, "count": 0}))
    monkeypatch.setattr(scorer, "_confidence_score", lambda *args, **kwargs: 0.5)

    result = scorer.score_case(case, fast_pass=False)

    assert result.score == 0.88
    assert result.components["override_applied"] is True


def test_media_mentions_caps_low_credibility_burst():
    now = datetime.now(timezone.utc)
    mentions = [
        SimpleNamespace(credibility_score=0.2, published_at=now - timedelta(hours=2), is_deleted=False)
        for _ in range(8)
    ]
    db = _DBStub(rows=mentions)
    scorer = CaseImportanceScorer(db)
    case = _make_case()

    score, meta = scorer._media_mentions_score(case, decay_lambda=0.05)

    assert meta["anti_gaming_cap_applied"] is True
    assert meta["low_cred_recent"] >= 6
    assert 0.0 <= score <= 1.0
