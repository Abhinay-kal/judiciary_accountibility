from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.feedback_auth import is_admin_actor
from app.core.monitoring import FEEDBACK_APPROVAL_SECONDS, FEEDBACK_MODERATION_ACTIONS_TOTAL, FEEDBACK_PENDING_QUEUE
from app.db.session import get_db
from app.models import CaseFeedback, FeedbackAuditAction, FeedbackVerificationMethod
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])


def _require_admin_id(body: dict) -> int:
    admin_id = int(body.get("admin_id") or 0)
    if not is_admin_actor(admin_id):
        raise HTTPException(status_code=422, detail="admin_id is required")
    return admin_id


@router.get("/pending")
def pending_feedback(
    case_id: int | None = Query(default=None),
    responder: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    service = FeedbackService(db)
    rows = service.list_pending_feedback(case_id=case_id, responder=responder)
    FEEDBACK_PENDING_QUEUE.set(len(rows))
    return {"items": rows, "total": len(rows)}


@router.post("/{feedback_id}/verify")
async def verify_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    method = body.get("method") or "admin_verified"
    reason = body.get("reason") or "Admin verification"

    verification_evidence: tuple[str, bytes] | None = None
    if body.get("verification_evidence_text"):
        text = str(body["verification_evidence_text"]).encode("utf-8")
        verification_evidence = ("verification-evidence.txt", text)

    try:
        result = service.admin_verify_feedback(
            feedback_id=feedback_id,
            admin_id=admin_id,
            method=FeedbackVerificationMethod(method),
            reason=reason,
            evidence_attachment=verification_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.VERIFIED.value).inc()
    return result


@router.post("/{feedback_id}/publish")
def publish_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    try:
        result = service.admin_publish_feedback(
            feedback_id=feedback_id,
            admin_id=admin_id,
            public_note=str(body.get("public_note") or "An official response was submitted and published."),
            redacted_content=body.get("redacted_content"),
            allow_unverified=bool(body.get("allow_unverified", False)),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    row = db.query(CaseFeedback).filter(CaseFeedback.id == feedback_id).one_or_none()
    if row is not None:
        FEEDBACK_APPROVAL_SECONDS.observe(max(0.0, (row.moderated_at - row.submitted_at).total_seconds()))

    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.PUBLISHED.value).inc()
    return result


@router.post("/{feedback_id}/reject")
def reject_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    reason = str(body.get("reason") or "Rejected by moderation team")
    try:
        result = service.admin_reject_feedback(feedback_id=feedback_id, admin_id=admin_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.REJECTED.value).inc()
    return result


@router.post("/{feedback_id}/limit")
def limit_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    reason = str(body.get("reason") or "Limited publication due to legal/privacy review")
    public_note = str(body.get("public_note") or "Response published in limited form pending legal review")
    redacted_content = str(body.get("redacted_content") or "")
    try:
        result = service.admin_limit_feedback(
            feedback_id=feedback_id,
            admin_id=admin_id,
            reason=reason,
            public_note=public_note,
            redacted_content=redacted_content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.LIMITED.value).inc()
    return result


@router.post("/{feedback_id}/escalate")
def escalate_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    reason = str(body.get("reason") or "Escalated to legal review")
    try:
        result = service.admin_escalate_feedback(feedback_id=feedback_id, admin_id=admin_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.ESCALATED.value).inc()
    return result


@router.post("/{feedback_id}/urgent-hide")
def urgent_hide_feedback(feedback_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    admin_id = _require_admin_id(body)
    reason = str(body.get("reason") or "Urgent legal takedown")
    try:
        result = service.admin_urgent_hide_feedback(feedback_id=feedback_id, admin_id=admin_id, reason=reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    FEEDBACK_MODERATION_ACTIONS_TOTAL.labels(action=FeedbackAuditAction.URGENT_HIDDEN.value).inc()
    return result


@router.get("/{feedback_id}/audit")
def feedback_audit_logs(feedback_id: str, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    return {"feedback_id": feedback_id, "items": service.get_feedback_audit_logs(feedback_id=feedback_id)}
