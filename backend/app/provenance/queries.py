from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.provenance.models import FieldProvenance


def get_field_provenance(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
) -> list[FieldProvenance]:
    return (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == entity_type,
            FieldProvenance.entity_id == entity_id,
            FieldProvenance.field_name == field_name,
        )
        .order_by(FieldProvenance.created_at.desc())
        .all()
    )


def get_entity_provenance(db: Session, *, entity_type: str, entity_id: str) -> list[FieldProvenance]:
    return (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == entity_type,
            FieldProvenance.entity_id == entity_id,
        )
        .order_by(FieldProvenance.field_name.asc(), FieldProvenance.created_at.desc())
        .all()
    )


def get_source_provenance(db: Session, *, source_id: str, limit: int = 200) -> list[FieldProvenance]:
    return (
        db.query(FieldProvenance)
        .filter(
            (FieldProvenance.source_name == source_id) | (FieldProvenance.ingestion_run_id == source_id)
        )
        .order_by(FieldProvenance.created_at.desc())
        .limit(limit)
        .all()
    )


def get_primary_for_field(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
    as_of: datetime | None = None,
) -> FieldProvenance | None:
    query = (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == entity_type,
            FieldProvenance.entity_id == entity_id,
            FieldProvenance.field_name == field_name,
        )
    )
    if as_of is not None:
        query = query.filter(FieldProvenance.created_at <= as_of)

    return (
        query.order_by(
            FieldProvenance.is_primary_source.desc(),
            FieldProvenance.confidence_score.desc(),
            FieldProvenance.fetch_time.desc().nullslast(),
            FieldProvenance.created_at.desc(),
        )
        .first()
    )
