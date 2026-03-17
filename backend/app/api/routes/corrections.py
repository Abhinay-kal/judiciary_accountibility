from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.monitoring import CORRECTION_REQUESTS_TOTAL, LEGAL_ESCALATIONS_TOTAL
from app.db.session import get_db
from app.moderation.admin_tools import apply_takedown, remove_label
from app.moderation.renderer import render_public_text
from app.models import (
    ContentLabelKind,
    CorrectionRequest,
    CorrectionRequestStatus,
    ModerationLog,
    ModerationActionType,
    ModerationTargetType,
    PublicStatus,
)
from app.moderation.admin_tools import add_manual_label, review_correction_request, write_moderation_log
from app.moderation.labeler import _target_row
from app.moderation.notifications import (
    notify_admin_new_correction,
    notify_legal_escalation,
    send_correction_acknowledgement,
)
from app.services.correction_templates import ADMIN_ACCEPT_TEMPLATE, ADMIN_REJECT_TEMPLATE, PUBLIC_CORRECTION_NOTE_TEMPLATE

router = APIRouter(prefix="/corrections", tags=["corrections"])
settings = get_settings()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _parse_target_type(value: str) -> ModerationTargetType:
    try:
        return ModerationTargetType(value.lower())
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid target_type") from exc


def _legal_risk(reason: str) -> bool:
    lowered = (reason or "").lower()
    return any(token in lowered for token in ["legal", "defamation", "pii", "privacy", "takedown", "notice"])


@router.post("/requests")
async def submit_correction_request(
    target_type: str = Form(...),
    target_id: int = Form(...),
    requester_name: str = Form(...),
    requester_contact: str = Form(...),
    requester_affiliation: str | None = Form(default=None),
    request_reason: str = Form(...),
    evidence_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    ttype = _parse_target_type(target_type)

    exists = _target_row(db, ttype, target_id)
    if exists is None:
        raise HTTPException(status_code=404, detail="Target content not found")

    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    monthly_for_target = (
        db.query(CorrectionRequest)
        .filter(
            CorrectionRequest.target_type == ttype,
            CorrectionRequest.target_id == target_id,
            CorrectionRequest.submitted_at >= month_ago,
        )
        .count()
    )
    if monthly_for_target >= settings.rate_limit_correction_requests_per_target_per_month:
        write_moderation_log(
            db,
            action_type=ModerationActionType.CORRECTION_HANDLED,
            target_type=ttype,
            target_id=target_id,
            admin_id=None,
            reason="Rate limit exceeded for correction submissions",
            payload={"requester_contact": requester_contact, "event": "rate_limited"},
        )
        db.commit()
        raise HTTPException(status_code=429, detail="Correction submission limit reached for this target")

    low_quality_recent = (
        db.query(CorrectionRequest)
        .filter(
            CorrectionRequest.requester_contact == requester_contact,
            CorrectionRequest.status == CorrectionRequestStatus.REJECTED,
            CorrectionRequest.submitted_at >= month_ago,
        )
        .count()
    )
    if low_quality_recent >= 5:
        write_moderation_log(
            db,
            action_type=ModerationActionType.CORRECTION_HANDLED,
            target_type=ttype,
            target_id=target_id,
            admin_id=None,
            reason="Submitter temporarily blocked due to repeated low-quality requests",
            payload={"requester_contact": requester_contact, "event": "abuse_block"},
        )
        db.commit()
        raise HTTPException(status_code=429, detail="Submitter temporarily blocked")

    upload_ref = None
    if evidence_file is not None:
        payload = await evidence_file.read()
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Attachment exceeds 10MB limit")
        upload_ref = f"corrections/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{evidence_file.filename or 'upload.bin'}"

    status = CorrectionRequestStatus.ESCALATED if _legal_risk(request_reason) else CorrectionRequestStatus.PENDING

    row = CorrectionRequest(
        target_type=ttype,
        target_id=target_id,
        requester_name=requester_name,
        requester_contact=requester_contact,
        requester_affiliation=requester_affiliation,
        request_reason=request_reason,
        evidence_upload_ref=upload_ref,
        status=status,
        review_notes={"intake": "received"},
    )
    db.add(row)
    db.flush()
    CORRECTION_REQUESTS_TOTAL.labels(status=row.status.value).inc()

    send_correction_acknowledgement(contact=requester_contact, request_id=row.id)
    notify_admin_new_correction(
        target_type=ttype.value,
        target_id=target_id,
        request_id=row.id,
        admin_contact=settings.notify_on_correction_email,
    )

    if status == CorrectionRequestStatus.ESCALATED:
        exists.public_status = PublicStatus.HIDDEN
        exists.public_note = "Content temporarily hidden pending legal-sensitive correction review."
        notify_legal_escalation(request_id=row.id, reason="Auto-escalated legal-sensitive correction request")
        LEGAL_ESCALATIONS_TOTAL.labels(reason="correction_request_legal_sensitive").inc()

    db.commit()
    return {
        "id": row.id,
        "status": row.status.value,
        "submitted_at": row.submitted_at,
        "message": "Correction request received",
    }


@router.get("/requests/{request_id}")
def correction_request_status(request_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(CorrectionRequest).filter(CorrectionRequest.id == request_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")

    return {
        "id": row.id,
        "target_type": row.target_type.value,
        "target_id": row.target_id,
        "status": row.status.value,
        "submitted_at": row.submitted_at,
        "resolved_at": row.resolved_at,
        "request_reason": row.request_reason[:400],
        "requester_affiliation": row.requester_affiliation,
    }


@router.get("/admin/corrections/pending")
def admin_pending_corrections(
    status: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    requester: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(CorrectionRequest)
    if status:
        query = query.filter(CorrectionRequest.status == CorrectionRequestStatus(status))
    else:
        query = query.filter(CorrectionRequest.status.in_([CorrectionRequestStatus.PENDING, CorrectionRequestStatus.IN_REVIEW, CorrectionRequestStatus.ESCALATED]))

    if target_type:
        query = query.filter(CorrectionRequest.target_type == _parse_target_type(target_type))
    if target_id is not None:
        query = query.filter(CorrectionRequest.target_id == target_id)
    if requester:
        query = query.filter(CorrectionRequest.requester_name.ilike(f"%{requester}%"))

    rows = query.order_by(CorrectionRequest.submitted_at.desc()).all()
    return {
        "items": [
            {
                "id": row.id,
                "target_type": row.target_type.value,
                "target_id": row.target_id,
                "requester_name": row.requester_name,
                "requester_contact": row.requester_contact,
                "request_reason": row.request_reason,
                "status": row.status.value,
                "submitted_at": row.submitted_at,
                "assigned_admin": row.assigned_admin,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.post("/admin/corrections/{request_id}/assign")
def assign_correction_request(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    row = db.query(CorrectionRequest).filter(CorrectionRequest.id == request_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")

    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")

    row.assigned_admin = admin_id
    if row.status == CorrectionRequestStatus.PENDING:
        row.status = CorrectionRequestStatus.IN_REVIEW

    db.commit()
    return {"id": row.id, "status": row.status.value, "assigned_admin": row.assigned_admin}


@router.post("/admin/corrections/{request_id}/review")
def review_correction_request_endpoint(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    row = db.query(CorrectionRequest).filter(CorrectionRequest.id == request_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")

    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")

    status_value = str(body.get("status") or "").upper()
    notes = body.get("notes") or {}
    reason = str(body.get("reason") or "Correction review update")

    try:
        status = CorrectionRequestStatus(status_value)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid review status") from exc

    updated = review_correction_request(
        db,
        request=row,
        status=status,
        notes=notes,
        admin_id=admin_id,
        reason=reason,
    )

    message = ADMIN_ACCEPT_TEMPLATE if status == CorrectionRequestStatus.ACCEPTED else ADMIN_REJECT_TEMPLATE
    db.commit()
    return {
        "id": updated.id,
        "status": updated.status.value,
        "message": message,
        "resolved_at": updated.resolved_at,
    }


@router.post("/admin/corrections/{request_id}/publish-response")
def publish_correction_response(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    row = db.query(CorrectionRequest).filter(CorrectionRequest.id == request_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Correction request not found")

    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")

    public_note = str(body.get("public_note") or PUBLIC_CORRECTION_NOTE_TEMPLATE)
    visibility = str(body.get("public_status") or "LIMITED").upper()

    try:
        public_status = PublicStatus(visibility)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid public_status") from exc

    target = _target_row(db, row.target_type, row.target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target no longer exists")

    target.public_note = public_note
    target.public_status = public_status

    add_manual_label(
        db=db,
        target_type=row.target_type,
        target_id=row.target_id,
        label=ContentLabelKind.VERIFIED if row.status == CorrectionRequestStatus.ACCEPTED else ContentLabelKind.REQUIRES_VERIFICATION,
        label_confidence=0.8 if row.status == CorrectionRequestStatus.ACCEPTED else 0.5,
        explanation="Correction response published by admin",
        admin_id=admin_id,
    )

    write_moderation_log(
        db,
        action_type=ModerationActionType.CONTENT_REDACED,
        target_type=row.target_type,
        target_id=row.target_id,
        admin_id=admin_id,
        reason="Published correction response and updated public note",
        payload={"request_id": row.id, "public_status": public_status.value},
    )

    db.commit()
    return {
        "request_id": row.id,
        "target_type": row.target_type.value,
        "target_id": row.target_id,
        "public_status": target.public_status.value,
        "public_note": target.public_note,
    }


@router.post("/admin/labels/add")
def admin_add_label(body: dict, db: Session = Depends(get_db)) -> dict:
    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")
    target_type = _parse_target_type(str(body.get("target_type") or ""))
    target_id = int(body.get("target_id") or 0)
    if target_id <= 0:
        raise HTTPException(status_code=422, detail="target_id is required")

    try:
        label = ContentLabelKind(str(body.get("label") or "UNVERIFIED").upper())
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid label") from exc

    explanation = str(body.get("explanation") or "Admin label decision")
    row = add_manual_label(
        db,
        target_type=target_type,
        target_id=target_id,
        label=label,
        label_confidence=float(body.get("label_confidence") or 0.6),
        explanation=explanation,
        admin_id=admin_id,
    )
    db.commit()
    return {"label_id": row.id, "label": row.label.value, "target_type": row.target_type.value, "target_id": row.target_id}


@router.post("/admin/labels/{label_id}/remove")
def admin_remove_label(label_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    admin_id = int(body.get("admin_id") or 0)
    reason = str(body.get("reason") or "Label removed by admin")
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")
    remove_label(db, label_id=label_id, admin_id=admin_id, reason=reason)
    db.commit()
    return {"label_id": label_id, "status": "removed"}


@router.post("/admin/redact")
def admin_redact_content(body: dict, db: Session = Depends(get_db)) -> dict:
    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")

    target_type = _parse_target_type(str(body.get("target_type") or ""))
    target_id = int(body.get("target_id") or 0)
    reason = str(body.get("reason") or "Redacted for legal-safe publication")
    raw_text = str(body.get("text") or "")

    target = _target_row(db, target_type, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target content not found")

    rendered, meta = render_public_text(raw_text, ["REQUIRES_VERIFICATION"], parser_confidence=0.0)
    target.public_note = rendered
    target.public_status = PublicStatus.LIMITED

    write_moderation_log(
        db,
        action_type=ModerationActionType.CONTENT_REDACED,
        target_type=target_type,
        target_id=target_id,
        admin_id=admin_id,
        reason=reason,
        payload={"redaction_meta": meta},
    )
    db.commit()
    return {"target_type": target_type.value, "target_id": target_id, "public_status": target.public_status.value, "public_note": target.public_note}


@router.post("/admin/takedown")
def admin_takedown(body: dict, db: Session = Depends(get_db)) -> dict:
    admin_id = int(body.get("admin_id") or 0)
    if admin_id <= 0:
        raise HTTPException(status_code=422, detail="admin_id is required")

    target_type = _parse_target_type(str(body.get("target_type") or ""))
    target_id = int(body.get("target_id") or 0)
    reason = str(body.get("reason") or "Legal takedown requested")

    apply_takedown(db, target_type=target_type, target_id=target_id, reason=reason, admin_id=admin_id)
    notify_legal_escalation(request_id=0, reason=reason)
    db.commit()
    return {"target_type": target_type.value, "target_id": target_id, "public_status": "HIDDEN"}


@router.get("/admin/moderation-logs")
def admin_moderation_logs(limit: int = 200, db: Session = Depends(get_db)) -> dict:
    rows = db.query(ModerationLog).order_by(ModerationLog.created_at.desc()).limit(max(1, min(limit, 1000))).all()
    return {
        "items": [
            {
                "id": row.id,
                "action_type": row.action_type.value,
                "target_type": row.target_type.value,
                "target_id": row.target_id,
                "admin_id": row.admin_id,
                "reason": row.reason,
                "payload": row.payload,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/admin/legal-queue")
def admin_legal_queue(db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(CorrectionRequest)
        .filter(CorrectionRequest.status == CorrectionRequestStatus.ESCALATED)
        .order_by(CorrectionRequest.submitted_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "request_id": row.id,
                "target_type": row.target_type.value,
                "target_id": row.target_id,
                "requester_name": row.requester_name,
                "request_reason": row.request_reason,
                "submitted_at": row.submitted_at,
                "evidence_upload_ref": row.evidence_upload_ref,
                "case_package": {
                    "timeline_endpoint": f"/api/v1/{row.target_type.value}s/{row.target_id}",
                    "correction_request_id": row.id,
                    "moderation_logs_endpoint": "/api/v1/corrections/admin/moderation-logs",
                },
            }
            for row in rows
        ],
        "total": len(rows),
    }
