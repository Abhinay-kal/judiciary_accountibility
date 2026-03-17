from __future__ import annotations

from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api.routes import corrections
from app.models import (
    Case,
    ContentLabel,
    ContentLabelKind,
    CorrectionRequest,
    CorrectionRequestStatus,
    ModerationTargetType,
    PublicStatus,
)
from app.moderation.labeler import label_content
from app.moderation.renderer import render_public_text


class _FakeQuery:
    def __init__(self, payload=None, counts=None):
        self.payload = payload
        self.counts = counts or [0]

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self.payload

    def count(self):
        if self.counts:
            return self.counts.pop(0)
        return 0

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        if isinstance(self.payload, list):
            return self.payload
        return []


class _FakeDB:
    def __init__(self, *, target=None, correction=None, counts=None):
        self.target = target
        self.correction = correction
        self.counts = counts or [0, 0]
        self.added = []

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == "CorrectionRequest":
            return _FakeQuery(self.correction, self.counts)
        return _FakeQuery(self.target)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, CorrectionRequest):
            self.correction = obj

    def flush(self):
        for idx, obj in enumerate(self.added, start=1):
            if getattr(obj, "id", None) is None:
                obj.id = idx

    def commit(self):
        return None



def _case() -> Case:
    return Case(
        case_uid="c-1",
        case_number="1/2025",
        court_id=1,
        court_level="district",
        state="Delhi",
        status="pending",
        source_url="https://example.com",
        filing_date=date(2025, 1, 1),
        source_fields={},
    )


def test_render_public_text_redacts_unverified_names() -> None:
    text, meta = render_public_text(
        "Ravi Sharma is guilty and proves corruption.",
        labels=["UNVERIFIED"],
        parser_confidence=0.4,
        source_links=["https://example.com"],
    )
    assert "name withheld" in text
    assert "indicates" in text
    assert meta["data_status"] == "Unverified"


def test_render_public_text_verified_keeps_text_but_neutralizes_verbs() -> None:
    text, meta = render_public_text(
        "Data proves unusual delay pattern caused by X.",
        labels=["VERIFIED"],
        parser_confidence=0.9,
    )
    assert "indicates" in text
    assert meta["data_status"] == "Verified"


def test_labeler_sets_data_anomaly_without_primary_source() -> None:
    case = _case()
    db = _FakeDB(target=case)
    label = label_content(
        db,
        target_type="case",
        target_id=1,
        evidence_bundle={"raw_text": "X took a bribe", "source_links": []},
        parser_confidence=0.9,
    )
    assert isinstance(label, ContentLabel)
    assert label.label == ContentLabelKind.DATA_ANOMALY
    assert case.public_status == PublicStatus.LIMITED


def test_labeler_marks_verified_when_corroborated() -> None:
    case = _case()
    db = _FakeDB(target=case)
    label = label_content(
        db,
        target_type="case",
        target_id=1,
        evidence_bundle={
            "raw_text": "Pattern in public records",
            "source_links": ["https://court.gov/record"],
            "primary_source_count": 1,
        },
        parser_confidence=0.92,
        ml_signals={"is_politician_related": True},
    )
    assert label.label == ContentLabelKind.VERIFIED


@pytest.mark.asyncio
async def test_correction_request_rate_limit_enforced(monkeypatch) -> None:
    case = _case()
    db = _FakeDB(target=case, counts=[3])
    monkeypatch.setattr(corrections, "_target_row", lambda *_args, **_kwargs: case)

    with pytest.raises(HTTPException) as exc:
        await corrections.submit_correction_request(
            target_type="case",
            target_id=1,
            requester_name="A",
            requester_contact="a@example.com",
            requester_affiliation=None,
            request_reason="Please correct",
            evidence_file=None,
            db=db,
        )
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_full_correction_lifecycle_submit_review_publish(monkeypatch) -> None:
    case = _case()
    db = _FakeDB(target=case, counts=[0, 0])
    monkeypatch.setattr(corrections, "_target_row", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(corrections, "send_correction_acknowledgement", lambda **_kwargs: None)
    monkeypatch.setattr(corrections, "notify_admin_new_correction", lambda **_kwargs: None)
    monkeypatch.setattr(corrections, "notify_legal_escalation", lambda **_kwargs: None)
    monkeypatch.setattr(corrections, "add_manual_label", lambda **_kwargs: None)

    upload = UploadFile(filename="evidence.pdf", file=BytesIO(b"pdf-bytes"))
    created = await corrections.submit_correction_request(
        target_type="case",
        target_id=1,
        requester_name="Reporter",
        requester_contact="reporter@example.com",
        requester_affiliation="NGO",
        request_reason="Factual correction requested",
        evidence_file=upload,
        db=db,
    )
    assert created["status"] in {"PENDING", "ESCALATED"}

    reviewed = corrections.review_correction_request_endpoint(
        request_id=1,
        body={"admin_id": 7, "status": "ACCEPTED", "reason": "Validated", "notes": {"ok": True}},
        db=db,
    )
    assert reviewed["status"] == "ACCEPTED"

    published = corrections.publish_correction_response(
        request_id=1,
        body={"admin_id": 7, "public_status": "LIMITED", "public_note": "Neutral correction published"},
        db=db,
    )
    assert published["public_status"] == "LIMITED"
    assert case.public_note == "Neutral correction published"


@pytest.mark.asyncio
async def test_legal_sensitive_request_auto_escalates_and_hides(monkeypatch) -> None:
    case = _case()
    db = _FakeDB(target=case, counts=[0, 0])
    monkeypatch.setattr(corrections, "_target_row", lambda *_args, **_kwargs: case)
    monkeypatch.setattr(corrections, "send_correction_acknowledgement", lambda **_kwargs: None)
    monkeypatch.setattr(corrections, "notify_admin_new_correction", lambda **_kwargs: None)
    monkeypatch.setattr(corrections, "notify_legal_escalation", lambda **_kwargs: None)

    created = await corrections.submit_correction_request(
        target_type="case",
        target_id=1,
        requester_name="Counsel",
        requester_contact="legal@example.com",
        requester_affiliation="Law firm",
        request_reason="Legal notice: remove PII and process immediate takedown",
        evidence_file=None,
        db=db,
    )
    assert created["status"] == "ESCALATED"
    assert case.public_status == PublicStatus.HIDDEN


def test_redaction_function_masks_names() -> None:
    text, meta = render_public_text(
        "Rahul Verma and Anita Kapoor are accused of fraud.",
        labels=["REQUIRES_VERIFICATION"],
        parser_confidence=0.5,
    )
    assert "name withheld" in text
    assert len(meta["redacted_names"]) >= 1
