from __future__ import annotations

from sqlalchemy.orm import Session

from app.provenance.models import FieldProvenance, ProvenanceLink


def find_field_conflicts(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
) -> list[dict]:
    rows = (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == entity_type,
            FieldProvenance.entity_id == entity_id,
            FieldProvenance.field_name == field_name,
        )
        .order_by(FieldProvenance.created_at.desc())
        .all()
    )
    if len(rows) <= 1:
        return []

    by_hash: dict[str, list[FieldProvenance]] = {}
    for item in rows:
        by_hash.setdefault(item.field_value_hash, []).append(item)

    if len(by_hash) <= 1:
        return []

    flattened = [item for group in by_hash.values() for item in group]
    return [
        {
            "provenance_id": item.provenance_id,
            "field_value_hash": item.field_value_hash,
            "source_name": item.source_name,
            "source_type": item.source_type,
            "fetch_time": item.fetch_time,
            "confidence_score": item.confidence_score,
            "is_primary_source": item.is_primary_source,
        }
        for item in flattened
    ]


def register_conflicts_for_new_record(db: Session, new_record: FieldProvenance) -> None:
    peers = (
        db.query(FieldProvenance)
        .filter(
            FieldProvenance.entity_type == new_record.entity_type,
            FieldProvenance.entity_id == new_record.entity_id,
            FieldProvenance.field_name == new_record.field_name,
            FieldProvenance.provenance_id != new_record.provenance_id,
        )
        .all()
    )
    for peer in peers:
        if peer.field_value_hash == new_record.field_value_hash:
            continue

        exists = (
            db.query(ProvenanceLink)
            .filter(
                ProvenanceLink.parent_provenance_id == new_record.provenance_id,
                ProvenanceLink.child_provenance_id == peer.provenance_id,
                ProvenanceLink.relationship_type == "CONFLICTS_WITH",
            )
            .one_or_none()
        )
        if exists is None:
            db.add(
                ProvenanceLink(
                    parent_provenance_id=new_record.provenance_id,
                    child_provenance_id=peer.provenance_id,
                    relationship_type="CONFLICTS_WITH",
                )
            )
