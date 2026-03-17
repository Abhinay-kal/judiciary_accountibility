from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Case,
    CaseFeedback,
    FeedbackAuditAction,
    FeedbackAuditLog,
    FeedbackDisplayLabel,
    FeedbackPublicStatus,
    FeedbackReceivedVia,
    FeedbackResponderType,
    FeedbackVerification,
    FeedbackVerificationMethod,
)
from app.notifications.feedback_notifications import (
    emit_feedback_published_webhook,
    notify_feedback_status_change,
    notify_feedback_token_sent,
    notify_pending_feedback_threshold,
)
from app.storage.feedback_attachments import sanitize_html_text, store_feedback_attachments
from app.storage.storage_client import StorageClient


@dataclass
class SubmitFeedbackResult:
    feedback_id: str
    verification_instructions: str
    verification_method: str


@dataclass
class VerificationResult:
    feedback_id: str
    verified: bool
    method: str


class FeedbackService:
    def __init__(self, db: Session, storage: StorageClient | None = None) -> None:
        self.db = db
        self.cfg = get_settings()
        self.storage = storage or StorageClient(base_dir="backend/raw_data")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _contact_hash(contact: str) -> str:
        return hashlib.sha256((contact or "").strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _encrypt_contact(contact: str) -> str:
        return base64.urlsafe_b64encode(contact.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decrypt_contact(ciphertext: str) -> str:
        return base64.urlsafe_b64decode(ciphertext.encode("ascii")).decode("utf-8")

    def _parse_domains(self, raw_domains: str) -> set[str]:
        return {item.strip().lower() for item in (raw_domains or "").split(",") if item.strip()}

    def _audit(
        self,
        *,
        feedback_id: str,
        action: FeedbackAuditAction,
        actor_id: int | None,
        reason: str | None,
        payload: dict | None = None,
    ) -> FeedbackAuditLog:
        row = FeedbackAuditLog(
            feedback_id=feedback_id,
            action=action,
            actor_id=actor_id,
            reason=reason,
            payload=payload or {},
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _assert_case_exists(self, case_id: int) -> Case:
        row = self.db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
        if row is None:
            raise ValueError("Case not found")
        return row

    def _enforce_rate_limit(self, *, contact_hash: str, case_id: int) -> None:
        month_ago = self._now() - timedelta(days=30)
        count = (
            self.db.query(CaseFeedback)
            .filter(
                CaseFeedback.case_id == case_id,
                CaseFeedback.responder_contact_hash == contact_hash,
                CaseFeedback.submitted_at >= month_ago,
            )
            .count()
        )
        if count >= self.cfg.feedback_rate_limit_per_contact_per_month:
            raise PermissionError("Feedback submission rate limit reached")

    def submit_case_feedback(
        self,
        *,
        case_id: int,
        responder_type: FeedbackResponderType,
        responder_name: str,
        responder_affiliation: str | None,
        responder_contact: str,
        content: str,
        preferred_display_label: FeedbackDisplayLabel,
        received_via: FeedbackReceivedVia,
        attachments: Iterable[tuple[str, bytes]],
        loa_upload: tuple[str, bytes] | None = None,
    ) -> SubmitFeedbackResult:
        self._assert_case_exists(case_id)
        contact_hash = self._contact_hash(responder_contact)
        self._enforce_rate_limit(contact_hash=contact_hash, case_id=case_id)

        sanitized_content = sanitize_html_text(content)
        if not sanitized_content:
            raise ValueError("Feedback content cannot be empty")

        encrypted_contact = self._encrypt_contact(responder_contact)
        domain = responder_contact.split("@")[-1].lower() if "@" in responder_contact else ""
        whitelisted = domain in self._parse_domains(self.cfg.feedback_whitelisted_domains)
        auto_verify = domain in self._parse_domains(self.cfg.feedback_auto_verify_domains)
        public_mail_domain = domain in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me", "protonmail.com"}
        official_claim_with_public_email = responder_type in {
            FeedbackResponderType.GOV_AGENCY,
            FeedbackResponderType.COMPANY,
            FeedbackResponderType.LAW_FIRM,
        } and public_mail_domain

        row = CaseFeedback(
            case_id=case_id,
            responder_type=responder_type,
            responder_name=sanitize_html_text(responder_name),
            responder_affiliation=sanitize_html_text(responder_affiliation or "") or None,
            responder_contact=encrypted_contact,
            responder_contact_hash=contact_hash,
            responder_verified=False,
            responder_verification_method=None,
            verification_confidence=0.6 if whitelisted else 0.2,
            content=sanitized_content,
            content_text_index=sanitized_content,
            attachments_ref=[],
            received_via=received_via,
            public_status=FeedbackPublicStatus.PENDING_REVIEW,
            public_note="A response has been submitted and is pending verification. We will update when verified.",
            display_label=preferred_display_label,
            moderation_notes={"domain": domain, "whitelisted_domain": whitelisted},
            is_private=True,
            loa_attachment_ref=None,
        )
        self.db.add(row)
        self.db.flush()

        attachment_refs = store_feedback_attachments(
            self.storage,
            feedback_id=row.id,
            attachments=attachments,
            is_public=False,
        )
        row.attachments_ref = attachment_refs

        if loa_upload is not None:
            loa_refs = store_feedback_attachments(
                self.storage,
                feedback_id=row.id,
                attachments=[loa_upload],
                is_public=False,
            )
            row.loa_attachment_ref = loa_refs[0]["storage_ref"]

        if official_claim_with_public_email and not row.loa_attachment_ref:
            row.moderation_notes = {
                **(row.moderation_notes or {}),
                "requires_loa_or_manual_verification": True,
                "public_email_domain_used": domain,
            }

        verify_token = secrets.token_urlsafe(32)
        verification = FeedbackVerification(
            feedback_id=row.id,
            method=FeedbackVerificationMethod.EMAIL_TOKEN,
            token=self._token_hash(verify_token),
            token_expires_at=self._now() + timedelta(hours=self.cfg.feedback_token_expiry_hours),
            metadata_json={"email": responder_contact, "domain": domain, "auto_verify": auto_verify},
        )
        self.db.add(verification)

        if auto_verify:
            verification.verified_at = self._now()
            row.responder_verified = True
            row.responder_verification_method = FeedbackVerificationMethod.DOMAIN_VERIFICATION
            row.verification_confidence = 0.9

        self._audit(
            feedback_id=row.id,
            action=FeedbackAuditAction.SUBMITTED,
            actor_id=None,
            reason="RtR feedback submitted",
            payload={"received_via": row.received_via.value, "attachment_count": len(attachment_refs)},
        )

        verify_url = f"/api/v1/feedback/{row.id}/verify-token?token={verify_token}"
        notify_feedback_token_sent(email=responder_contact, feedback_id=row.id, verify_url=verify_url)

        pending_count = self.db.query(CaseFeedback).filter(CaseFeedback.public_status == FeedbackPublicStatus.PENDING_REVIEW).count()
        if pending_count >= 20:
            notify_pending_feedback_threshold(pending_count=pending_count)

        self.db.commit()
        return SubmitFeedbackResult(
            feedback_id=row.id,
            verification_instructions=(
                "Check your email for a verification link. "
                "If using a public mailbox, upload a letter of authority for priority verification."
            ),
            verification_method="domain_verification" if auto_verify else "email_token",
        )

    def verify_feedback_token(self, *, feedback_id: str, token: str) -> VerificationResult:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")

        token_hash = self._token_hash(token)
        verification = (
            self.db.query(FeedbackVerification)
            .filter(
                FeedbackVerification.feedback_id == feedback_id,
                FeedbackVerification.token == token_hash,
                FeedbackVerification.method == FeedbackVerificationMethod.EMAIL_TOKEN,
            )
            .order_by(FeedbackVerification.id.desc())
            .first()
        )
        if verification is None:
            raise PermissionError("Invalid verification token")
        if verification.verified_at is not None:
            raise PermissionError("Token already used")
        if verification.token_expires_at and verification.token_expires_at < self._now():
            raise PermissionError("Token expired")

        verification.verified_at = self._now()
        row.responder_verified = True
        row.responder_verification_method = FeedbackVerificationMethod.EMAIL_TOKEN
        row.verification_confidence = max(row.verification_confidence, 0.8)

        self._audit(
            feedback_id=row.id,
            action=FeedbackAuditAction.VERIFIED,
            actor_id=None,
            reason="Email token verified",
            payload={"method": FeedbackVerificationMethod.EMAIL_TOKEN.value},
        )

        contact = self._decrypt_contact(row.responder_contact)
        notify_feedback_status_change(email=contact, feedback_id=row.id, status="verified")
        self.db.commit()
        return VerificationResult(feedback_id=row.id, verified=True, method=FeedbackVerificationMethod.EMAIL_TOKEN.value)

    def get_case_feedback_list(self, *, case_id: int, include_non_public: bool = False) -> list[dict]:
        query = self.db.query(CaseFeedback).filter(CaseFeedback.case_id == case_id)
        if not include_non_public:
            query = query.filter(CaseFeedback.public_status.in_([FeedbackPublicStatus.PUBLISHED, FeedbackPublicStatus.LIMITED]))

        rows = query.order_by(CaseFeedback.submitted_at.desc()).all()
        output: list[dict] = []
        for row in rows:
            attachment_refs = row.attachments_ref or []
            public_attachments = [item for item in attachment_refs if item.get("public")]
            output.append(
                {
                    "id": row.id,
                    "case_id": row.case_id,
                    "responder_name": row.responder_name if (row.responder_verified or row.public_status == FeedbackPublicStatus.PUBLISHED) else "Name withheld",
                    "responder_affiliation": row.responder_affiliation,
                    "responder_type": row.responder_type.value,
                    "responder_verified": row.responder_verified,
                    "responder_verification_method": row.responder_verification_method.value if row.responder_verification_method else None,
                    "submitted_at": row.submitted_at,
                    "display_label": row.display_label.value,
                    "public_status": row.public_status.value,
                    "public_note": row.public_note,
                    "content": row.content if row.public_status == FeedbackPublicStatus.PUBLISHED else None,
                    "attachments": public_attachments,
                    "placeholder": (
                        "A response has been submitted by "
                        f"{row.responder_affiliation or 'an authorized party'} and is under review."
                    )
                    if row.public_status == FeedbackPublicStatus.PENDING_REVIEW
                    else None,
                }
            )
        return output

    def get_feedback_detail(self, *, feedback_id: str, owner_contact: str | None = None) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")

        if row.public_status in {FeedbackPublicStatus.PUBLISHED, FeedbackPublicStatus.LIMITED}:
            for item in self.get_case_feedback_list(case_id=row.case_id, include_non_public=True):
                if item["id"] == row.id:
                    return item

        if not owner_contact or self._contact_hash(owner_contact) != row.responder_contact_hash:
            raise PermissionError("Not authorized to view private feedback")

        return {
            "id": row.id,
            "case_id": row.case_id,
            "responder_name": row.responder_name,
            "responder_affiliation": row.responder_affiliation,
            "responder_verified": row.responder_verified,
            "responder_verification_method": row.responder_verification_method.value if row.responder_verification_method else None,
            "submitted_at": row.submitted_at,
            "public_status": row.public_status.value,
            "public_note": row.public_note,
            "content": row.content,
            "attachments": row.attachments_ref,
            "is_private": row.is_private,
            "moderation_notes": row.moderation_notes,
        }

    def admin_verify_feedback(
        self,
        *,
        feedback_id: str,
        admin_id: int,
        method: FeedbackVerificationMethod,
        reason: str,
        evidence_attachment: tuple[str, bytes] | None = None,
    ) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")

        metadata = {"reason": reason}
        if evidence_attachment is not None:
            refs = store_feedback_attachments(
                self.storage,
                feedback_id=feedback_id,
                attachments=[evidence_attachment],
                is_public=False,
            )
            metadata["verification_evidence"] = refs[0]

        verification = FeedbackVerification(
            feedback_id=feedback_id,
            method=method,
            token=self._token_hash(secrets.token_urlsafe(24)),
            token_expires_at=None,
            verified_at=self._now(),
            verifier_admin_id=admin_id,
            metadata_json=metadata,
        )
        self.db.add(verification)

        row.responder_verified = True
        row.responder_verification_method = method
        row.verification_confidence = 1.0
        row.moderator_id = admin_id
        row.moderated_at = self._now()

        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.VERIFIED,
            actor_id=admin_id,
            reason=reason,
            payload={"method": method.value},
        )

        contact = self._decrypt_contact(row.responder_contact)
        notify_feedback_status_change(email=contact, feedback_id=row.id, status="verified", note=reason)
        self.db.commit()
        return {"id": row.id, "responder_verified": row.responder_verified, "method": method.value}

    def admin_publish_feedback(
        self,
        *,
        feedback_id: str,
        admin_id: int,
        public_note: str,
        redacted_content: str | None = None,
        allow_unverified: bool = False,
    ) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")
        if not row.responder_verified and not allow_unverified:
            raise PermissionError("Verification required before publish")

        row.public_status = FeedbackPublicStatus.PUBLISHED
        row.is_private = False
        row.moderator_id = admin_id
        row.moderated_at = self._now()
        row.public_note = sanitize_html_text(public_note)
        if redacted_content:
            row.moderation_notes = {
                **(row.moderation_notes or {}),
                "published_redacted_version": sanitize_html_text(redacted_content),
            }

        refs = []
        for item in row.attachments_ref or []:
            updated = dict(item)
            updated["public"] = True
            refs.append(updated)
        row.attachments_ref = refs

        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.PUBLISHED,
            actor_id=admin_id,
            reason="Published feedback",
            payload={"allow_unverified": allow_unverified, "public_note": row.public_note},
        )

        contact = self._decrypt_contact(row.responder_contact)
        notify_feedback_status_change(email=contact, feedback_id=row.id, status="published", note=row.public_note)
        submitted_at = row.submitted_at or self._now()
        emit_feedback_published_webhook(
            {
                "event": "feedback_published",
                "feedback_id": row.id,
                "case_id": row.case_id,
                "submitted_at": submitted_at.isoformat(),
                "responder_affiliation": row.responder_affiliation,
                "verification_method": row.responder_verification_method.value if row.responder_verification_method else None,
            }
        )

        self.db.commit()
        return {"id": row.id, "public_status": row.public_status.value, "public_note": row.public_note}

    def admin_reject_feedback(self, *, feedback_id: str, admin_id: int, reason: str) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")
        row.public_status = FeedbackPublicStatus.REJECTED
        row.moderator_id = admin_id
        row.moderated_at = self._now()
        row.moderation_notes = {**(row.moderation_notes or {}), "rejection_reason": reason}

        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.REJECTED,
            actor_id=admin_id,
            reason=reason,
            payload={},
        )

        contact = self._decrypt_contact(row.responder_contact)
        notify_feedback_status_change(email=contact, feedback_id=row.id, status="rejected", note=reason)
        self.db.commit()
        return {"id": row.id, "public_status": row.public_status.value}

    def admin_limit_feedback(self, *, feedback_id: str, admin_id: int, reason: str, public_note: str, redacted_content: str) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")
        row.public_status = FeedbackPublicStatus.LIMITED
        row.is_private = False
        row.public_note = sanitize_html_text(public_note)
        row.moderator_id = admin_id
        row.moderated_at = self._now()
        row.moderation_notes = {
            **(row.moderation_notes or {}),
            "limited_reason": reason,
            "limited_content": sanitize_html_text(redacted_content),
        }

        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.LIMITED,
            actor_id=admin_id,
            reason=reason,
            payload={"public_note": row.public_note},
        )
        contact = self._decrypt_contact(row.responder_contact)
        notify_feedback_status_change(email=contact, feedback_id=row.id, status="limited", note=reason)
        self.db.commit()
        return {"id": row.id, "public_status": row.public_status.value, "public_note": row.public_note}

    def admin_escalate_feedback(self, *, feedback_id: str, admin_id: int, reason: str) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")

        row.legal_escalated = True
        row.moderation_notes = {**(row.moderation_notes or {}), "legal_escalation_reason": reason}
        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.ESCALATED,
            actor_id=admin_id,
            reason=reason,
            payload={},
        )
        self.db.commit()
        return {"id": row.id, "legal_escalated": True}

    def admin_urgent_hide_feedback(self, *, feedback_id: str, admin_id: int, reason: str) -> dict:
        row = self.db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
        if row is None:
            raise ValueError("Feedback not found")

        row.urgent_hidden = True
        row.is_private = True
        row.public_status = FeedbackPublicStatus.LIMITED
        row.moderation_notes = {**(row.moderation_notes or {}), "urgent_hidden_reason": reason}
        self._audit(
            feedback_id=feedback_id,
            action=FeedbackAuditAction.URGENT_HIDDEN,
            actor_id=admin_id,
            reason=reason,
            payload={},
        )
        self.db.commit()
        return {"id": row.id, "urgent_hidden": True}

    def list_pending_feedback(self, *, case_id: int | None = None, responder: str | None = None) -> list[dict]:
        query = self.db.query(CaseFeedback).filter(CaseFeedback.public_status == FeedbackPublicStatus.PENDING_REVIEW)
        if case_id is not None:
            query = query.filter(CaseFeedback.case_id == case_id)
        if responder:
            query = query.filter(CaseFeedback.responder_name.ilike(f"%{responder}%"))

        rows = query.order_by(CaseFeedback.submitted_at.desc()).all()
        items = []
        for row in rows:
            items.append(
                {
                    "id": row.id,
                    "case_id": row.case_id,
                    "responder_type": row.responder_type.value,
                    "responder_name": row.responder_name,
                    "responder_affiliation": row.responder_affiliation,
                    "responder_contact": self._decrypt_contact(row.responder_contact),
                    "responder_verified": row.responder_verified,
                    "submitted_at": row.submitted_at,
                    "public_status": row.public_status.value,
                    "attachments": row.attachments_ref,
                    "loa_attachment_ref": row.loa_attachment_ref,
                    "moderation_notes": row.moderation_notes,
                }
            )
        return items

    def get_feedback_audit_logs(self, *, feedback_id: str) -> list[dict]:
        rows = (
            self.db.query(FeedbackAuditLog)
            .filter(FeedbackAuditLog.feedback_id == feedback_id)
            .order_by(FeedbackAuditLog.created_at.desc())
            .all()
        )
        return [
            {
                "id": item.id,
                "action": item.action.value,
                "actor_id": item.actor_id,
                "reason": item.reason,
                "payload": item.payload,
                "created_at": item.created_at,
            }
            for item in rows
        ]
