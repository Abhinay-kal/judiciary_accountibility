from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models import (
    Case,
    CaseFeedback,
    FeedbackAuditAction,
    FeedbackDisplayLabel,
    FeedbackPublicStatus,
    FeedbackReceivedVia,
    FeedbackResponderType,
    FeedbackVerification,
    FeedbackVerificationMethod,
)
from app.services.feedback_service import FeedbackService
from app.storage.feedback_attachments import sanitize_html_text, scan_attachment


class _Query:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self.items[0] if self.items else None

    def first(self):
        return self.items[0] if self.items else None

    def count(self):
        return len(self.items)

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.items)


class _DB:
    def __init__(self):
        self.cases = []
        self.feedback = []
        self.verifications = []
        self.audits = []

    def add(self, obj):
        if obj.__class__.__name__ == "CaseFeedback":
            self.feedback.append(obj)
        elif obj.__class__.__name__ == "FeedbackVerification":
            self.verifications.append(obj)
        elif obj.__class__.__name__ == "FeedbackAuditLog":
            self.audits.append(obj)

    def flush(self):
        for row in self.feedback:
            if not row.id:
                row.id = str(uuid.uuid4())
        for idx, row in enumerate(self.verifications, start=1):
            if getattr(row, "id", None) is None:
                row.id = idx
        for idx, row in enumerate(self.audits, start=1):
            if getattr(row, "id", None) is None:
                row.id = idx

    def query(self, model):
        name = model.__name__
        if name == "Case":
            return _Query(self.cases)
        if name == "CaseFeedback":
            return _Query(self.feedback)
        if name == "FeedbackVerification":
            return _Query(self.verifications)
        if name == "FeedbackAuditLog":
            return _Query(self.audits)
        return _Query([])

    def commit(self):
        return None


class _StorageStub:
    def put_bytes(self, key: str, payload: bytes, *, tier: str = "hot", compress: bool = False):
        return key


def _case() -> Case:
    return Case(
        case_uid="c-rtr-1",
        case_number="1/2026",
        court_id=1,
        court_level="district",
        state="Delhi",
        status="pending",
        source_url="https://example.org/case/1",
        source_fields={},
    )


def _service(db: _DB) -> FeedbackService:
    db.cases = [_case()]
    return FeedbackService(db, storage=_StorageStub())


def test_submission_flow_generates_token_and_audit():
    db = _DB()
    service = _service(db)

    result = service.submit_case_feedback(
        case_id=1,
        responder_type=FeedbackResponderType.GOV_AGENCY,
        responder_name="Dept Officer",
        responder_affiliation="Dept of Personnel",
        responder_contact="officer@gov.in",
        content="<b>Official clarification</b>",
        preferred_display_label=FeedbackDisplayLabel.OFFICIAL_RESPONSE,
        received_via=FeedbackReceivedVia.WEB,
        attachments=[("note.txt", b"record")],
        loa_upload=None,
    )

    assert result.feedback_id
    assert db.feedback[0].content == "Official clarification"
    assert db.verifications and db.verifications[0].token
    assert db.audits and db.audits[0].action == FeedbackAuditAction.SUBMITTED


def test_email_token_verification_happy_expired_reused():
    db = _DB()
    service = _service(db)
    submit = service.submit_case_feedback(
        case_id=1,
        responder_type=FeedbackResponderType.INDIVIDUAL,
        responder_name="A",
        responder_affiliation="Aff",
        responder_contact="user@example.com",
        content="content",
        preferred_display_label=FeedbackDisplayLabel.RESPONSE_FROM_PARTY,
        received_via=FeedbackReceivedVia.API,
        attachments=[],
        loa_upload=None,
    )

    token = "token-1"
    db.verifications[0].token = service._token_hash(token)
    db.verifications[0].token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    ok = service.verify_feedback_token(feedback_id=submit.feedback_id, token=token)
    assert ok.verified is True

    with pytest.raises(PermissionError):
        service.verify_feedback_token(feedback_id=submit.feedback_id, token=token)

    db.verifications[0].verified_at = None
    db.verifications[0].token = service._token_hash("token-2")
    db.verifications[0].token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(PermissionError):
        service.verify_feedback_token(feedback_id=submit.feedback_id, token="token-2")


def test_admin_publish_and_reject_create_audit_logs():
    db = _DB()
    service = _service(db)
    submit = service.submit_case_feedback(
        case_id=1,
        responder_type=FeedbackResponderType.COMPANY,
        responder_name="Company Rep",
        responder_affiliation="Entity Pvt Ltd",
        responder_contact="rep@entity.com",
        content="Official response body",
        preferred_display_label=FeedbackDisplayLabel.OFFICIAL_RESPONSE,
        received_via=FeedbackReceivedVia.WEB,
        attachments=[],
        loa_upload=None,
    )

    db.feedback[0].responder_verified = True
    service.admin_publish_feedback(
        feedback_id=submit.feedback_id,
        admin_id=10,
        public_note="An official response was submitted by Entity Pvt Ltd.",
    )
    assert any(item.action == FeedbackAuditAction.PUBLISHED for item in db.audits)

    service.admin_reject_feedback(feedback_id=submit.feedback_id, admin_id=10, reason="duplicate")
    assert any(item.action == FeedbackAuditAction.REJECTED for item in db.audits)


def test_attachment_security_and_sanitization():
    assert sanitize_html_text("<script>alert(1)</script><b>Hello</b>") == "Hello"
    with pytest.raises(ValueError):
        scan_attachment("payload.exe", b"x")


def test_rate_limit_enforcement():
    db = _DB()
    service = _service(db)
    for _ in range(service.cfg.feedback_rate_limit_per_contact_per_month):
        db.feedback.append(
            SimpleNamespace(
                id=str(uuid.uuid4()),
                case_id=1,
                responder_contact_hash=service._contact_hash("a@b.com"),
                submitted_at=datetime.now(timezone.utc),
                public_status=FeedbackPublicStatus.PENDING_REVIEW,
            )
        )

    with pytest.raises(PermissionError):
        service.submit_case_feedback(
            case_id=1,
            responder_type=FeedbackResponderType.INDIVIDUAL,
            responder_name="New",
            responder_affiliation="Aff",
            responder_contact="a@b.com",
            content="new content",
            preferred_display_label=FeedbackDisplayLabel.RESPONSE_FROM_PARTY,
            received_via=FeedbackReceivedVia.WEB,
            attachments=[],
            loa_upload=None,
        )


def test_end_to_end_submit_verify_publish_public_list_and_loa_path():
    db = _DB()
    service = _service(db)

    # Email token path
    submit = service.submit_case_feedback(
        case_id=1,
        responder_type=FeedbackResponderType.GOV_AGENCY,
        responder_name="Officer",
        responder_affiliation="Agency",
        responder_contact="officer@agency.gov.in",
        content="Statement body",
        preferred_display_label=FeedbackDisplayLabel.OFFICIAL_RESPONSE,
        received_via=FeedbackReceivedVia.WEB,
        attachments=[],
        loa_upload=None,
    )
    token = "happy-token"
    db.verifications[0].token = service._token_hash(token)
    db.verifications[0].token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    service.verify_feedback_token(feedback_id=submit.feedback_id, token=token)
    service.admin_publish_feedback(feedback_id=submit.feedback_id, admin_id=1, public_note="Published note")

    rows = service.get_case_feedback_list(case_id=1, include_non_public=False)
    assert rows and rows[0]["public_status"] in {"PUBLISHED", "LIMITED"}

    # LOA path with admin verify
    submit_loa = service.submit_case_feedback(
        case_id=1,
        responder_type=FeedbackResponderType.LAW_FIRM,
        responder_name="Counsel",
        responder_affiliation="Law Firm",
        responder_contact="counsel@gmail.com",
        content="Lawful response",
        preferred_display_label=FeedbackDisplayLabel.RESPONSE_FROM_PARTY,
        received_via=FeedbackReceivedVia.UPLOAD,
        attachments=[],
        loa_upload=("loa.pdf", b"pdf-bytes"),
    )
    verify = service.admin_verify_feedback(
        feedback_id=submit_loa.feedback_id,
        admin_id=5,
        method=FeedbackVerificationMethod.LETTER_OF_AUTHORITY,
        reason="LOA reviewed",
        evidence_attachment=("check.txt", b"verified"),
    )
    assert verify["responder_verified"] is True
