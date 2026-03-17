from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.monitoring import CONTENT_LABELS_TOTAL, CONTENT_TAKEDOWNS_TOTAL
from app.models import (
    ContentLabel,
    ContentLabelKind,
    ContentLabelSource,
    CorrectionRequest,
    CorrectionRequestStatus,
    ModerationActionType,
    ModerationLog,
    ModerationTargetType,
    PublicStatus,
)


def write_moderation_log(
    db: Session,
    *,
    action_type: ModerationActionType,
    target_type: ModerationTargetType,
    target_id: int,
    reason: str,
    admin_id: int | None,
    payload: dict | None = None,
) -> ModerationLog:
    row = ModerationLog(
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        admin_id=admin_id,
        payload=payload or {},
    )
    db.add(row)
    db.flush()
    return row


def add_manual_label(
    db: Session,
    *,
    target_type: ModerationTargetType,
    target_id: int,
    label: ContentLabelKind,
    label_confidence: float,
    explanation: str,
    admin_id: int,
) -> ContentLabel:
    row = ContentLabel(
        target_type=target_type,
        target_id=target_id,
        label=label,
        label_source=ContentLabelSource.MANUAL,
        label_confidence=max(0.0, min(1.0, label_confidence)),
        created_by=admin_id,
        metadata_json={"label_explanation": explanation},
    )
    db.add(row)
    db.flush()
    CONTENT_LABELS_TOTAL.labels(label=row.label.value).inc()
    write_moderation_log(
        db,
        action_type=ModerationActionType.LABEL_ADDED,
        target_type=target_type,
        target_id=target_id,
        reason=explanation,
        admin_id=admin_id,
        payload={"label": label.value, "confidence": row.label_confidence},
    )
    return row


def remove_label(db: Session, *, label_id: int, admin_id: int, reason: str) -> None:
    row = db.query(ContentLabel).filter(ContentLabel.id == label_id).one_or_none()
    if row is None:
        raise ValueError("Label not found")
    write_moderation_log(
        db,
        action_type=ModerationActionType.LABEL_REMOVED,
        target_type=row.target_type,
        target_id=row.target_id,
        reason=reason,
        admin_id=admin_id,
        payload={"label_id": row.id, "label": row.label.value},
    )
    db.delete(row)


def apply_takedown(
    db: Session,
    *,
    target_type: ModerationTargetType,
    target_id: int,
    reason: str,
    admin_id: int,
) -> None:
    from app.moderation.labeler import _target_row

    row = _target_row(db, target_type, target_id)
    if row is None:
        raise ValueError("Target not found")

    row.public_status = PublicStatus.HIDDEN
    row.public_note = "Content hidden pending legal review."
    CONTENT_TAKEDOWNS_TOTAL.labels(target_type=target_type.value).inc()
    write_moderation_log(
        db,
        action_type=ModerationActionType.TAKEDOWN,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        admin_id=admin_id,
        payload={"public_status": PublicStatus.HIDDEN.value},
    )


def review_correction_request(
    db: Session,
    *,
    request: CorrectionRequest,
    status: CorrectionRequestStatus,
    notes: dict,
    admin_id: int,
    reason: str,
) -> CorrectionRequest:
    request.status = status
    request.review_notes = notes
    request.resolved_at = datetime.now(timezone.utc)
    request.assigned_admin = admin_id

    write_moderation_log(
        db,
        action_type=ModerationActionType.CORRECTION_HANDLED,
        target_type=request.target_type,
        target_id=request.target_id,
        reason=reason,
        admin_id=admin_id,
        payload={"request_id": request.id, "status": status.value, "notes": notes},
    )
    return request
