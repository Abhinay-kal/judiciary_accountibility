from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin_hearings
from app.db.session import get_db
from app.ingestion.hearing_outcomes import (
    CorroboratingSignal,
    ParseResult,
    annotate_hearing,
    coerce_corroborating_signals,
    parse_outcome_text,
)
from app.main import app
from app.models import HearingOutcomeType


@pytest.mark.parametrize(
    ("text", "expected", "minimum_confidence"),
    [
        ("Matter adjourned to next week", HearingOutcomeType.ADJOURNED, 0.95),
        ("Case postponed due to strike", HearingOutcomeType.ADJOURNED, 0.95),
        ("Deferred for compliance", HearingOutcomeType.ADJOURNED, 0.95),
        ("Put up on 22.03.2026", HearingOutcomeType.ADJOURNED, 0.95),
        ("Relisted after summer break", HearingOutcomeType.ADJOURNED, 0.95),
        ("ADJD. at request of parties", HearingOutcomeType.ADJOURNED, 0.95),
        ("Arguments heard", HearingOutcomeType.HEARD, 0.92),
        ("Argument heard and matter considered", HearingOutcomeType.HEARD, 0.92),
        ("Taken up and heard today", HearingOutcomeType.HEARD, 0.92),
        ("Order reserved", HearingOutcomeType.ORDER_RESERVED, 0.93),
        ("Orders reserved after hearing", HearingOutcomeType.ORDER_RESERVED, 0.93),
        ("Order kept for pronouncement", HearingOutcomeType.ORDER_RESERVED, 0.93),
        ("Disposed of finally", HearingOutcomeType.DISPOSED, 0.96),
        ("Dismissed with costs", HearingOutcomeType.DISPOSED, 0.96),
        ("Judgment pronounced in open court", HearingOutcomeType.DISPOSED, 0.96),
        ("Allowed in part", HearingOutcomeType.DISPOSED, 0.96),
        ("Not reached today", HearingOutcomeType.NOT_REACHED, 0.90),
        ("Case not taken up", HearingOutcomeType.NOT_REACHED, 0.90),
        ("No proceedings due to boycott", HearingOutcomeType.NO_PROCEEDINGS, 0.90),
        ("Not heard on account of paucity of time", HearingOutcomeType.NOT_REACHED, 0.90),
        ("", HearingOutcomeType.LISTED, 0.85),
        ("Item No. 14 for hearing", HearingOutcomeType.LISTED, 0.85),
        ("कार्यवाही स्थगित", HearingOutcomeType.OTHER, 0.50),
        ("Matter mentioned", HearingOutcomeType.OTHER, 0.50),
    ],
)
def test_rule_engine_examples(text: str, expected: HearingOutcomeType, minimum_confidence: float) -> None:
    result = parse_outcome_text(text, listing_type="daily cause list", source_name="high_court", allow_ml=False)
    assert result.outcome_type == expected
    assert result.confidence >= minimum_confidence or expected == HearingOutcomeType.OTHER


def test_order_pdf_confirmation_overrides_listing_to_disposed() -> None:
    result = parse_outcome_text(
        "Item No. 32 for hearing",
        listing_type="cause list",
        source_name="high_court",
        has_order_pdf=True,
        corroborating_signals=[
            CorroboratingSignal(
                outcome_type=HearingOutcomeType.DISPOSED,
                confidence=0.99,
                source_name="orders",
                evidence_id="order:7",
                matched_keywords=["judgment"],
                matched_rules=["order_pdf_disposal"],
            )
        ],
        allow_ml=False,
    )
    assert result.outcome_type == HearingOutcomeType.DISPOSED
    assert result.confidence == pytest.approx(0.99)
    assert "order_pdf_override" in result.matched_rules


def test_multi_source_corroboration_boosts_confidence() -> None:
    result = parse_outcome_text(
        "Arguments heard",
        source_name="judge_diary",
        corroborating_signals=[
            CorroboratingSignal(
                outcome_type=HearingOutcomeType.HEARD,
                confidence=0.86,
                source_name="news",
                evidence_id="news:11",
            )
        ],
        allow_ml=False,
    )
    assert result.outcome_type == HearingOutcomeType.HEARD
    assert result.confidence > 0.92
    assert "multi_source_corroboration" in result.matched_rules


def test_conflicting_tokens_prefers_disposal_rule() -> None:
    result = parse_outcome_text(
        "Case not heard earlier but judgment pronounced today",
        source_name="high_court",
        allow_ml=False,
    )
    assert result.outcome_type == HearingOutcomeType.DISPOSED
    assert result.confidence >= 0.96


def test_coerce_corroborating_signals_handles_payload_dicts() -> None:
    payloads = [
        {
            "outcome_type": "heard",
            "confidence": "0.88",
            "source": "judge_diary",
            "evidence_id": "diary:20",
            "matched_keywords": ["heard today"],
            "matched_rules": ["judge_diary_entry"],
        },
        {
            "outcome_type": "disposed",
            "confidence": 1.5,
            "source_name": "news",
        },
        {
            "outcome_type": "invalid_type",
            "confidence": 0.8,
        },
    ]

    signals = coerce_corroborating_signals(payloads)
    assert len(signals) == 2
    assert signals[0].outcome_type == HearingOutcomeType.HEARD
    assert signals[0].confidence == pytest.approx(0.88)
    assert signals[0].source_name == "judge_diary"
    assert signals[1].outcome_type == HearingOutcomeType.DISPOSED
    assert signals[1].confidence == pytest.approx(1.0)


class FakeDB:
    def __init__(self, hearing=None, audits=None):
        self.hearing = hearing
        self.audits = audits or []
        self.added = []

    def add(self, obj):
        self.added.append(obj)
        if hasattr(obj, "hearing_id"):
            self.audits.append(obj)

    def flush(self):
        for index, audit in enumerate(self.audits, start=1):
            if getattr(audit, "id", None) is None:
                audit.id = index

    def get(self, model, item_id):
        return self.hearing if self.hearing and self.hearing.id == item_id else None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def query(self, model):
        if model is admin_hearings.HearingOutcomeAudit:
            return FakeQuery(self.audits)
        raise AssertionError(f"Unexpected query model: {model}")


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.items)

    def limit(self, _limit):
        return self


def test_annotate_hearing_records_audit() -> None:
    hearing = SimpleNamespace(
        id=4,
        case_id=2,
        outcome_type=HearingOutcomeType.LISTED,
        outcome_confidence=0.42,
        annotated_by=None,
        annotated_at=None,
        parser_version="outcome-rules-v1",
    )
    db = FakeDB(hearing=hearing)
    audit = annotate_hearing(
        db,
        hearing=hearing,
        outcome_type=HearingOutcomeType.HEARD,
        explanation="Verified against order sheet",
        admin_id=91,
    )
    assert hearing.outcome_type == HearingOutcomeType.HEARD
    assert hearing.outcome_confidence == 1.0
    assert hearing.annotated_by == 91
    assert audit.previous_outcome_type == HearingOutcomeType.LISTED
    assert audit.new_outcome_type == HearingOutcomeType.HEARD


@pytest.fixture
def client_with_admin_overrides(monkeypatch):
    hearing = SimpleNamespace(
        id=10,
        case_id=50,
        date=date(2026, 3, 17),
        listing_type="cause list",
        outcome_text="Item No. 1 for hearing",
        raw_outcome_text="Item No. 1 for hearing",
        outcome_type=HearingOutcomeType.LISTED,
        outcome_confidence=0.4,
        parser_version="outcome-rules-v1",
        annotated_by=None,
        annotated_at=None,
        source="high_court",
        is_deleted=False,
    )
    fake_db = FakeDB(hearing=hearing)

    def _get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _get_db

    monkeypatch.setattr(
        admin_hearings,
        "build_hearing_evidence_bundle",
        lambda db, hearing: {"why": "Matched listing_only", "needs_verification": True},
    )

    def _annotate(db, hearing, outcome_type, explanation, admin_id):
        hearing.outcome_type = outcome_type
        hearing.outcome_confidence = 1.0
        hearing.annotated_by = admin_id
        hearing.annotated_at = datetime(2026, 3, 17)
        return SimpleNamespace(
            id=1,
            action="annotate",
            admin_id=admin_id,
            explanation=explanation,
            previous_outcome_type=HearingOutcomeType.LISTED,
            new_outcome_type=outcome_type,
            previous_confidence=0.4,
            new_confidence=1.0,
            previous_parser_version="outcome-rules-v1",
            new_parser_version="outcome-rules-v1-manual",
            changed_at=datetime(2026, 3, 17),
        )

    monkeypatch.setattr(admin_hearings, "annotate_hearing", _annotate)
    monkeypatch.setattr(
        admin_hearings,
        "reprocess_hearing",
        lambda db, hearing, parser_version=None, admin_id=None, explanation=None: (
            ParseResult(
                outcome_type=HearingOutcomeType.DISPOSED,
                confidence=0.99,
                matched_rules=["order_pdf_override"],
                matched_keywords=["judgment"],
                evidence_ids=["order:1"],
                source_names=["orders"],
                parser_version=parser_version or "outcome-rules-v2",
                explanation="Order PDF corroborated disposal on the same hearing date.",
            ),
            SimpleNamespace(
                id=2,
                action="reprocess",
                admin_id=admin_id,
                explanation=explanation,
                previous_outcome_type=HearingOutcomeType.LISTED,
                new_outcome_type=HearingOutcomeType.DISPOSED,
                previous_confidence=0.4,
                new_confidence=0.99,
                previous_parser_version="outcome-rules-v1",
                new_parser_version=parser_version or "outcome-rules-v2",
                changed_at=datetime(2026, 3, 17),
            ),
        ),
    )
    monkeypatch.setattr(
        admin_hearings,
        "review_queue_query",
        lambda db, threshold: FakeQuery([hearing]),
    )

    client = TestClient(app)
    try:
        yield client, fake_db
    finally:
        app.dependency_overrides.clear()


def test_admin_annotate_endpoint(client_with_admin_overrides) -> None:
    client, _fake_db = client_with_admin_overrides
    response = client.post(
        "/api/v1/admin/hearings/10/annotate",
        json={"outcome_type": "HEARD", "explanation": "Verified manually", "admin_id": 7},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["hearing"]["outcome_type"] == "HEARD"
    assert payload["audit"]["new_outcome_type"] == "HEARD"


def test_admin_review_endpoint(client_with_admin_overrides) -> None:
    client, _fake_db = client_with_admin_overrides
    response = client.get("/api/v1/admin/hearings/review?threshold=0.6")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["outcome_type"] == "LISTED"


def test_admin_reprocess_endpoint(client_with_admin_overrides) -> None:
    client, _fake_db = client_with_admin_overrides
    response = client.post(
        "/api/v1/admin/hearings/10/reprocess",
        json={"parser_version": "outcome-rules-v2", "admin_id": 13},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["parse_result"]["outcome_type"] == "DISPOSED"
    assert payload["audit"]["new_parser_version"] == "outcome-rules-v2"


def test_admin_audit_endpoint(client_with_admin_overrides) -> None:
    client, fake_db = client_with_admin_overrides
    fake_db.audits.append(
        SimpleNamespace(
            id=5,
            action="annotate",
            admin_id=3,
            explanation="Manual confirmation",
            previous_outcome_type=HearingOutcomeType.LISTED,
            new_outcome_type=HearingOutcomeType.DISPOSED,
            previous_confidence=0.4,
            new_confidence=1.0,
            previous_parser_version="outcome-rules-v1",
            new_parser_version="outcome-rules-v1-manual",
            changed_at=datetime(2026, 3, 17),
        )
    )
    response = client.get("/api/v1/admin/hearings/10/audit")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["new_outcome_type"] == "DISPOSED"


def test_ml_fallback_train_and_predict(tmp_path) -> None:
    from app.ml.hearing_outcomes import OutcomeMLParser

    parser = OutcomeMLParser()
    parser.settings = SimpleNamespace(
        ml_artifacts_dir=str(tmp_path),
        ml_parser_artifact_name="hearing_outcome_model.pkl",
        ml_parser_report_name="hearing_outcome_evaluation.json",
        ml_parser_enabled=True,
    )

    annotated_hearings = []
    for index in range(4):
        annotated_hearings.append(
            SimpleNamespace(
                raw_outcome_text=f"Matter adjourned to {index + 1} April",
                outcome_text=f"Matter adjourned to {index + 1} April",
                source="high_court",
                parser_version="outcome-rules-v1",
                outcome_type=HearingOutcomeType.ADJOURNED,
                annotated_by=1,
                case_id=index,
                date=date(2026, 3, 17),
                is_deleted=False,
            )
        )
        annotated_hearings.append(
            SimpleNamespace(
                raw_outcome_text=f"Judgment pronounced in open court {index}",
                outcome_text=f"Judgment pronounced in open court {index}",
                source="high_court",
                parser_version="outcome-rules-v1",
                outcome_type=HearingOutcomeType.DISPOSED,
                annotated_by=2,
                case_id=index + 10,
                date=date(2026, 3, 18),
                is_deleted=False,
            )
        )

    class MLFakeQuery:
        def __init__(self, items, first_result=None):
            self.items = items
            self.first_result = first_result

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.items)

        def first(self):
            return self.first_result

    class MLFakeDB:
        def query(self, model):
            if model.__name__ == "Hearing":
                return MLFakeQuery(annotated_hearings)
            return MLFakeQuery([], None)

    report = parser.train_from_annotations(MLFakeDB())
    assert report["trained"] is True
    prediction = parser.predict(
        raw_outcome_text="Judgment pronounced in open court",
        source_type="high_court",
        parser_version="outcome-rules-v1",
        presence_of_order_pdf=False,
    )
    assert prediction is not None
    assert prediction.outcome_type in {HearingOutcomeType.ADJOURNED, HearingOutcomeType.DISPOSED}
    assert prediction.confidence > 0.5