from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.monitoring import CONTENT_LABELS_TOTAL
from app.models import ContentLabel, ContentLabelKind, ContentLabelSource, Flag, ModerationTargetType, PublicStatus
from app.moderation.phrases import detect_risky_phrasing, has_primary_source_link


def _infer_target_type(target_type: str) -> ModerationTargetType:
    return ModerationTargetType(str(target_type).lower())


def _target_row(db: Session, target_type: ModerationTargetType, target_id: int) -> Any:
    if target_type == ModerationTargetType.CASE:
        from app.models import Case

        return db.query(Case).filter(Case.id == target_id, Case.is_deleted.is_(False)).one_or_none()
    if target_type == ModerationTargetType.FLAG:
        return db.query(Flag).filter(Flag.id == target_id, Flag.is_deleted.is_(False)).one_or_none()
    if target_type == ModerationTargetType.EVIDENCE:
        from app.models import Order

        return db.query(Order).filter(Order.id == target_id, Order.is_deleted.is_(False)).one_or_none()
    if target_type == ModerationTargetType.HEARING:
        from app.models import Hearing

        return db.query(Hearing).filter(Hearing.id == target_id, Hearing.is_deleted.is_(False)).one_or_none()
    return None


def label_content(
    db: Session,
    target_type: str,
    target_id: int,
    evidence_bundle: dict | None,
    parser_confidence: float,
    ml_signals: dict | None = None,
) -> ContentLabel:
    settings = get_settings()
    mode = settings.defamation_mode.lower()
    min_conf = settings.defamation_min_confidence_to_show_name
    ttype = _infer_target_type(target_type)
    target = _target_row(db, ttype, target_id)
    if target is None:
        raise ValueError(f"Unknown moderation target: {target_type}:{target_id}")

    ml = ml_signals or {}
    evidence_bundle = evidence_bundle or {}
    confidence = max(0.0, min(1.0, float(parser_confidence)))

    primary_source = has_primary_source_link(evidence_bundle)
    corroborated_primary = bool(primary_source and (evidence_bundle.get("primary_source_count") or 0) >= 1)
    risky = detect_risky_phrasing(str(evidence_bundle.get("raw_outcome_text") or evidence_bundle.get("raw_text") or ""))

    label = ContentLabelKind.UNVERIFIED
    explanation = "Defaulted to unverified due to missing verification context."

    if ttype == ModerationTargetType.FLAG and confidence < min_conf:
        label = ContentLabelKind.UNVERIFIED
        explanation = "Automated flag with low parser confidence; kept unverified."
    elif ml.get("is_politician_related") and confidence >= min_conf and corroborated_primary:
        label = ContentLabelKind.VERIFIED
        explanation = "Politician-linked entry is corroborated by primary source evidence."
    elif not primary_source or ml.get("conflicting_sources"):
        label = ContentLabelKind.REQUIRES_VERIFICATION
        explanation = "Evidence is missing or conflicting across sources."

    if risky.has_high_risk_language and not primary_source:
        label = ContentLabelKind.DATA_ANOMALY
        target.public_status = PublicStatus.LIMITED
        target.public_note = "Limited visibility pending source verification and legal-safe review."
        explanation = "High-risk allegation language found without primary source link; limited public visibility."

    if mode == "strict" and label != ContentLabelKind.VERIFIED:
        target.public_status = PublicStatus.LIMITED

    metadata = {
        "label_explanation": explanation,
        "rule_context": {
            "mode": mode,
            "parser_confidence": confidence,
            "primary_source": primary_source,
            "corroborated_primary": corroborated_primary,
            "ml_signals": ml,
            "risky_keywords": risky.matched_keywords,
            "risky_patterns": risky.matched_patterns,
            "accusation_score": risky.accusation_score,
        },
        "provenance_links": evidence_bundle.get("source_links") or [],
    }

    row = ContentLabel(
        target_type=ttype,
        target_id=target_id,
        label=label,
        label_source=ContentLabelSource.AUTOMATED,
        label_confidence=confidence,
        metadata_json=metadata,
    )
    db.add(row)
    db.flush()
    CONTENT_LABELS_TOTAL.labels(label=row.label.value).inc()

    target.last_label_id = row.id
    target.last_label_at = datetime.now(timezone.utc)

    db.flush()
    return row
