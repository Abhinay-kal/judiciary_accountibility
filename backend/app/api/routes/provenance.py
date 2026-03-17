from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Case
from app.provenance.conflict import find_field_conflicts
from app.provenance.lineage import trace_lineage_chain
from app.provenance.queries import get_entity_provenance, get_field_provenance, get_primary_for_field, get_source_provenance
from app.provenance.reconstruction import reconstruct_entity_state

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get("/field", response_model=dict)
def provenance_for_field(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    field_name: str = Query(...),
    include_lineage: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    rows = get_field_provenance(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No provenance records found")

    primary = get_primary_for_field(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
    )
    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "field_name": field_name,
        "primary_provenance_id": primary.provenance_id if primary else None,
        "records": [
            {
                "provenance_id": row.provenance_id,
                "field_value_hash": row.field_value_hash,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "source_url": row.source_url,
                "raw_payload_ref": row.raw_payload_ref,
                "extraction_method": row.extraction_method,
                "parser_version": row.parser_version,
                "fetch_time": row.fetch_time,
                "ingestion_run_id": row.ingestion_run_id,
                "confidence_score": row.confidence_score,
                "transformation_steps": row.transformation_steps,
                "is_primary_source": row.is_primary_source,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "conflicts": find_field_conflicts(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
        ),
    }
    if include_lineage and primary is not None:
        payload["lineage"] = trace_lineage_chain(db, provenance_id=primary.provenance_id)
    return payload


@router.get("/source/{source_id}", response_model=dict)
def provenance_by_source(source_id: str, limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db)) -> dict:
    rows = get_source_provenance(db, source_id=source_id, limit=limit)
    return {
        "source_id": source_id,
        "count": len(rows),
        "records": [
            {
                "provenance_id": row.provenance_id,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "field_name": row.field_name,
                "field_value_hash": row.field_value_hash,
                "fetch_time": row.fetch_time,
                "confidence_score": row.confidence_score,
                "source_name": row.source_name,
                "source_type": row.source_type,
            }
            for row in rows
        ],
    }


@router.get("/entity/{entity_type}/{entity_id}/reconstruct", response_model=dict)
def reconstruct_entity(entity_type: str, entity_id: str, db: Session = Depends(get_db)) -> dict:
    return reconstruct_entity_state(db, entity_type=entity_type, entity_id=entity_id)


@router.get("/cases/{case_id}", response_model=dict)
def provenance_for_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    rows = get_entity_provenance(db, entity_type="CASE", entity_id=str(case_id))
    by_field: dict[str, list[dict]] = {}
    for row in rows:
        by_field.setdefault(row.field_name, []).append(
            {
                "provenance_id": row.provenance_id,
                "field_value_hash": row.field_value_hash,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "source_url": row.source_url,
                "raw_payload_ref": row.raw_payload_ref,
                "fetch_time": row.fetch_time,
                "confidence_score": row.confidence_score,
                "is_primary_source": row.is_primary_source,
                "transformation_steps": row.transformation_steps,
                "created_at": row.created_at,
            }
        )

    conflicts = {
        field: find_field_conflicts(db, entity_type="CASE", entity_id=str(case_id), field_name=field)
        for field in by_field
    }
    primary = {
        field: get_primary_for_field(db, entity_type="CASE", entity_id=str(case_id), field_name=field).provenance_id
        for field in by_field
        if get_primary_for_field(db, entity_type="CASE", entity_id=str(case_id), field_name=field) is not None
    }

    return {
        "case_id": case_id,
        "fields": by_field,
        "primary_source_map": primary,
        "conflicts": conflicts,
    }
