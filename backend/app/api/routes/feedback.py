from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.monitoring import FEEDBACK_PENDING_QUEUE, FEEDBACK_SUBMISSIONS_TOTAL, FEEDBACK_VERIFICATIONS_TOTAL
from app.db.session import get_db
from app.models import CaseFeedback, FeedbackDisplayLabel, FeedbackPublicStatus, FeedbackReceivedVia, FeedbackResponderType
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _parse_enum(enum_type, value: str, field: str):
    try:
        return enum_type(value)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field}") from exc


@router.post("/case/{case_id}")
async def submit_feedback(
    case_id: int,
    responder_name: str = Form(...),
    responder_affiliation: str | None = Form(default=None),
    responder_contact: str = Form(...),
    responder_type: str = Form(...),
    content: str = Form(...),
    preferred_display_label: str = Form(default="RESPONSE_FROM_PARTY"),
    received_via: str = Form(default="WEB"),
    attachments: list[UploadFile] = File(default=[]),
    letter_of_authority_upload: UploadFile | None = File(default=None),
    x_captcha_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    cfg = get_settings()
    if cfg.feedback_enable_captcha_for_anonymous and not x_captcha_token:
        raise HTTPException(status_code=422, detail="CAPTCHA token required")

    if len(attachments) > cfg.feedback_max_attachments:
        raise HTTPException(status_code=413, detail=f"Max {cfg.feedback_max_attachments} attachments allowed")

    parsed_attachments: list[tuple[str, bytes]] = []
    total_bytes = 0
    per_file_limit = cfg.feedback_max_attachment_size_mb * 1024 * 1024
    total_limit = cfg.feedback_attachment_total_limit_mb * 1024 * 1024

    for item in attachments:
        payload = await item.read()
        if len(payload) > per_file_limit:
            raise HTTPException(status_code=413, detail=f"Attachment exceeds {cfg.feedback_max_attachment_size_mb}MB")
        total_bytes += len(payload)
        parsed_attachments.append((item.filename or "attachment.bin", payload))

    loa_payload: tuple[str, bytes] | None = None
    if letter_of_authority_upload is not None:
        loa_bytes = await letter_of_authority_upload.read()
        total_bytes += len(loa_bytes)
        loa_payload = (letter_of_authority_upload.filename or "loa.pdf", loa_bytes)

    if total_bytes > total_limit:
        raise HTTPException(status_code=413, detail=f"Combined uploads exceed {cfg.feedback_attachment_total_limit_mb}MB")

    try:
        service = FeedbackService(db)
        result = service.submit_case_feedback(
            case_id=case_id,
            responder_type=_parse_enum(FeedbackResponderType, responder_type, "responder_type"),
            responder_name=responder_name,
            responder_affiliation=responder_affiliation,
            responder_contact=responder_contact,
            content=content,
            preferred_display_label=_parse_enum(FeedbackDisplayLabel, preferred_display_label, "preferred_display_label"),
            received_via=_parse_enum(FeedbackReceivedVia, received_via, "received_via"),
            attachments=parsed_attachments,
            loa_upload=loa_payload,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    FEEDBACK_SUBMISSIONS_TOTAL.labels(
        responder_type=responder_type,
        received_via=received_via,
    ).inc()
    pending_count = db.query(CaseFeedback).filter(CaseFeedback.public_status == FeedbackPublicStatus.PENDING_REVIEW).count()
    FEEDBACK_PENDING_QUEUE.set(pending_count)

    return {
        "feedback_id": result.feedback_id,
        "verification_instructions": result.verification_instructions,
        "verification_method": result.verification_method,
    }


@router.get("/case/{case_id}")
def list_case_feedback(
    case_id: int,
    include_non_public: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    service = FeedbackService(db)
    rows = service.get_case_feedback_list(case_id=case_id, include_non_public=include_non_public)
    return {"case_id": case_id, "items": rows, "total": len(rows)}


@router.get("/{feedback_id}")
def feedback_detail(
    feedback_id: str,
    owner_contact: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    service = FeedbackService(db)
    try:
        return service.get_feedback_detail(feedback_id=feedback_id, owner_contact=owner_contact)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{feedback_id}/verify-token")
def verify_feedback_token(feedback_id: str, token: str, db: Session = Depends(get_db)) -> dict:
    service = FeedbackService(db)
    try:
        result = service.verify_feedback_token(feedback_id=feedback_id, token=token)
    except PermissionError as exc:
        FEEDBACK_VERIFICATIONS_TOTAL.labels(method="email_token", result="failed").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    FEEDBACK_VERIFICATIONS_TOTAL.labels(method=result.method, result="success").inc()
    return {"feedback_id": result.feedback_id, "verified": result.verified, "method": result.method}
