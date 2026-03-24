from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache import invalidate_namespace
from app.core.config import get_settings
from app.db.session import get_db
from app.evidence.hearings import build_hearing_evidence_bundle
from app.ingestion.hearing_outcomes import annotate_hearing, reprocess_hearing, review_queue_query
from datetime import datetime

from app.models import Hearing, HearingOutcomeAudit, HearingOutcomeType, JudgeAssignment, JudgeAssignmentRole, JudgeAttributionAudit, JudgeRegistry

router = APIRouter(prefix="/admin/hearings", tags=["admin-hearings"])
settings = get_settings()


@router.get("/review")
def list_hearings_for_review(
    threshold: float = Query(default=settings.default_outcome_confidence_verify, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hearings = review_queue_query(db, threshold).limit(limit).all()
    return {
        "threshold": threshold,
        "total": len(hearings),
        "items": [_serialize_hearing(db, hearing) for hearing in hearings],
    }


@router.post("/{hearing_id}/annotate")
def annotate_hearing_endpoint(
    hearing_id: int,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.is_deleted:
        raise HTTPException(status_code=404, detail="Hearing not found")
    try:
        outcome_type = HearingOutcomeType((body.get("outcome_type") or "").upper())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid outcome_type") from exc

    admin_id = body.get("admin_id")
    if admin_id is None:
        raise HTTPException(status_code=422, detail="admin_id is required")

    audit = annotate_hearing(
        db,
        hearing=hearing,
        outcome_type=outcome_type,
        explanation=body.get("explanation"),
        admin_id=int(admin_id),
    )
    db.commit()
    db.refresh(hearing)
    invalidate_namespace("case_timeline")
    invalidate_namespace("case")
    return {
        "hearing": _serialize_hearing(db, hearing),
        "audit": _serialize_audit(audit),
    }


@router.post("/{hearing_id}/reprocess")
def reprocess_hearing_endpoint(
    hearing_id: int,
    body: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.is_deleted:
        raise HTTPException(status_code=404, detail="Hearing not found")
    payload = body or {}
    result, audit = reprocess_hearing(
        db,
        hearing=hearing,
        parser_version=payload.get("parser_version"),
        admin_id=payload.get("admin_id"),
        explanation=payload.get("explanation"),
    )
    db.commit()
    db.refresh(hearing)
    invalidate_namespace("case_timeline")
    invalidate_namespace("case")
    return {
        "hearing": _serialize_hearing(db, hearing),
        "parse_result": result.to_dict(),
        "audit": _serialize_audit(audit),
    }


@router.get("/{hearing_id}/audit")
def get_hearing_audit(hearing_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.is_deleted:
        raise HTTPException(status_code=404, detail="Hearing not found")
    audits = (
        db.query(HearingOutcomeAudit)
        .filter(HearingOutcomeAudit.hearing_id == hearing_id)
        .order_by(HearingOutcomeAudit.changed_at.desc())
        .all()
    )
    return {"hearing_id": hearing_id, "items": [_serialize_audit(audit) for audit in audits]}


@router.post("/{hearing_id}/assign-judge")
def assign_judge_to_hearing(
    hearing_id: int,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.is_deleted:
        raise HTTPException(status_code=404, detail="Hearing not found")

    judge_registry_id = body.get("judge_registry_id")
    admin_id = body.get("admin_id")
    explanation = body.get("explanation") or "manual hearing judge assignment"
    if judge_registry_id is None or admin_id is None:
        raise HTTPException(status_code=422, detail="judge_registry_id and admin_id are required")

    registry = db.get(JudgeRegistry, judge_registry_id)
    if registry is None:
        raise HTTPException(status_code=404, detail="Judge registry entry not found")

    try:
        role = JudgeAssignmentRole((body.get("role") or "OTHER").upper())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid role") from exc

    sequence_index = int(body.get("sequence_index") or 0)
    existing = (
        db.query(JudgeAssignment)
        .filter(
            JudgeAssignment.hearing_id == hearing_id,
            JudgeAssignment.judge_id == judge_registry_id,
            JudgeAssignment.sequence_index == sequence_index,
        )
        .first()
    )

    if existing is None:
        assignment = JudgeAssignment(
            hearing_id=hearing_id,
            judge_id=judge_registry_id,
            judge_name_raw=body.get("judge_name_raw") or registry.canonical_name,
            role=role,
            is_presiding=role == JudgeAssignmentRole.PRESIDING,
            sequence_index=sequence_index,
            attribution_confidence=1.0,
            matched_on="manual",
            annotated_by=admin_id,
            annotated_at=datetime.utcnow(),
            parser_version=body.get("parser_version") or "manual",
            metadata_json={"manual_override": True},
        )
        db.add(assignment)
        db.flush()
        old_value = {}
    else:
        old_value = {
            "judge_name_raw": existing.judge_name_raw,
            "role": existing.role.value,
            "attribution_confidence": existing.attribution_confidence,
        }
        existing.judge_name_raw = body.get("judge_name_raw") or existing.judge_name_raw
        existing.role = role
        existing.is_presiding = role == JudgeAssignmentRole.PRESIDING
        existing.attribution_confidence = 1.0
        existing.matched_on = "manual"
        existing.annotated_by = admin_id
        existing.annotated_at = datetime.utcnow()
        existing.parser_version = body.get("parser_version") or "manual"
        assignment = existing

    db.add(
        JudgeAttributionAudit(
            action="manual_assign",
            hearing_id=hearing_id,
            assignment_id=assignment.assignment_id,
            judge_registry_id=judge_registry_id,
            admin_id=admin_id,
            reason=explanation,
            old_value=old_value,
            new_value={
                "judge_name_raw": assignment.judge_name_raw,
                "role": assignment.role.value,
                "attribution_confidence": assignment.attribution_confidence,
            },
        )
    )
    db.commit()
    invalidate_namespace("case_timeline")
    invalidate_namespace("judge")
    return {
        "hearing_id": hearing_id,
        "assignment_id": assignment.assignment_id,
        "judge_registry_id": assignment.judge_id,
        "role": assignment.role.value,
    }


def _serialize_hearing(db: Session, hearing: Hearing) -> dict[str, Any]:
    return {
        "id": hearing.id,
        "case_id": hearing.case_id,
        "date": hearing.date,
        "listing_type": hearing.listing_type,
        "outcome_text": hearing.outcome_text,
        "raw_outcome_text": hearing.raw_outcome_text,
        "outcome_type": hearing.outcome_type.value if hearing.outcome_type else None,
        "outcome_confidence": hearing.outcome_confidence,
        "needs_verification": (
            hearing.outcome_type is None
            or hearing.outcome_type == HearingOutcomeType.OTHER
            or (hearing.outcome_confidence or 0.0) < settings.default_outcome_confidence_verify
        ),
        "parser_version": hearing.parser_version,
        "annotated_by": hearing.annotated_by,
        "annotated_at": hearing.annotated_at,
        "source": hearing.source,
        "evidence_bundle": build_hearing_evidence_bundle(db, hearing),
    }


def _serialize_audit(audit: HearingOutcomeAudit) -> dict[str, Any]:
    return {
        "id": audit.id,
        "action": audit.action,
        "admin_id": audit.admin_id,
        "explanation": audit.explanation,
        "previous_outcome_type": audit.previous_outcome_type.value if audit.previous_outcome_type else None,
        "new_outcome_type": audit.new_outcome_type.value if audit.new_outcome_type else None,
        "previous_confidence": audit.previous_confidence,
        "new_confidence": audit.new_confidence,
        "previous_parser_version": audit.previous_parser_version,
        "new_parser_version": audit.new_parser_version,
        "changed_at": audit.changed_at,
    }