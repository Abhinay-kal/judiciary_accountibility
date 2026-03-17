from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.provenance.conflict import register_conflicts_for_new_record
from app.provenance.models import FieldProvenance, ProvenanceLink

_SOURCE_TYPE_WEIGHT = {
    "API": 1.0,
    "PDF": 0.92,
    "HTML": 0.82,
    "MANUAL": 0.7,
}


def hash_field_value(value: Any) -> str:
    """Stable hash for scalar/object field values used in provenance matching."""

    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _entry_rank(entry: FieldProvenance) -> float:
    source_weight = _SOURCE_TYPE_WEIGHT.get((entry.source_type or "").upper(), 0.5)
    recency_bonus = 0.0
    if entry.fetch_time is not None:
        age_days = max(0.0, (datetime.now(timezone.utc) - entry.fetch_time).total_seconds() / 86400.0)
        recency_bonus = max(0.0, 0.25 - min(0.25, age_days / 365.0))
    official_bonus = 0.05 if "court" in (entry.source_name or "").lower() else 0.0
    return (entry.confidence_score * 0.7) + (source_weight * 0.25) + recency_bonus + official_bonus


def _is_new_primary(db: Session, candidate: FieldProvenance) -> bool:
    rows = (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == candidate.entity_type,
            FieldProvenance.entity_id == candidate.entity_id,
            FieldProvenance.field_name == candidate.field_name,
        )
        .all()
    )
    if not rows:
        return True
    return _entry_rank(candidate) >= max(_entry_rank(item) for item in rows)


def record_field_provenance(
    db: Session,
    *,
    entity_type: str,
    entity_id: str | int,
    field_name: str,
    value: Any,
    source_name: str,
    source_type: str,
    source_url: str | None = None,
    raw_payload_ref: str | None = None,
    extraction_method: str | None = None,
    parser_version: str | None = None,
    fetch_time: datetime | None = None,
    ingestion_run_id: str | None = None,
    confidence_score: float = 0.0,
    transformation_steps: list[dict] | None = None,
    mark_primary: bool = True,
) -> FieldProvenance:
    entry = FieldProvenance(
        entity_type=entity_type,
        entity_id=str(entity_id),
        field_name=field_name,
        field_value_hash=hash_field_value(value),
        source_name=source_name,
        source_type=source_type,
        source_url=source_url,
        raw_payload_ref=raw_payload_ref,
        extraction_method=extraction_method,
        parser_version=parser_version,
        fetch_time=fetch_time,
        ingestion_run_id=ingestion_run_id,
        confidence_score=max(0.0, min(1.0, confidence_score)),
        transformation_steps=transformation_steps or [{"step": "capture", "output_value": value}],
        is_primary_source=False,
    )
    if mark_primary:
        entry.is_primary_source = _is_new_primary(db, entry)

    db.add(entry)
    db.flush()
    register_conflicts_for_new_record(db, entry)
    return entry


def link_provenance(
    db: Session,
    *,
    parent_provenance_id: int,
    child_provenance_id: int,
    relationship_type: str,
) -> ProvenanceLink:
    row = ProvenanceLink(
        parent_provenance_id=parent_provenance_id,
        child_provenance_id=child_provenance_id,
        relationship_type=relationship_type,
    )
    db.add(row)
    db.flush()
    return row


def record_derived_field_provenance(
    db: Session,
    *,
    entity_type: str,
    entity_id: str | int,
    field_name: str,
    derived_value: Any,
    parent_provenance_ids: list[int],
    source_name: str = "derived_pipeline",
    source_type: str = "API",
    extraction_method: str = "derived_calculation",
    parser_version: str | None = None,
    confidence_score: float = 0.7,
    transformation_steps: list[dict] | None = None,
    ingestion_run_id: str | None = None,
) -> FieldProvenance:
    derived = record_field_provenance(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        value=derived_value,
        source_name=source_name,
        source_type=source_type,
        extraction_method=extraction_method,
        parser_version=parser_version,
        ingestion_run_id=ingestion_run_id,
        confidence_score=confidence_score,
        transformation_steps=transformation_steps
        or [{"step": "derived_calculation", "output_value": derived_value}],
    )
    for parent_id in parent_provenance_ids:
        link_provenance(
            db,
            parent_provenance_id=parent_id,
            child_provenance_id=derived.provenance_id,
            relationship_type="DERIVED_FROM",
        )
    return derived
