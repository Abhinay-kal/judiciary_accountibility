from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.provenance.queries import get_entity_provenance


def _extract_value(row) -> object:
    steps = row.transformation_steps or []
    for step in reversed(steps):
        if isinstance(step, dict) and "output_value" in step:
            return step["output_value"]
        if isinstance(step, dict) and "value" in step:
            return step["value"]
    return None


def reconstruct_entity_state(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    as_of: datetime | None = None,
) -> dict:
    rows = get_entity_provenance(db, entity_type=entity_type, entity_id=entity_id)
    if as_of is not None:
        rows = [row for row in rows if row.created_at <= as_of]

    by_field: dict[str, list] = {}
    for row in rows:
        by_field.setdefault(row.field_name, []).append(row)

    state = {}
    provenance_index = {}
    for field, items in by_field.items():
        ranked = sorted(
            items,
            key=lambda x: (
                x.is_primary_source,
                x.confidence_score,
                x.fetch_time or x.created_at,
                x.created_at,
            ),
            reverse=True,
        )
        selected = ranked[0]
        state[field] = _extract_value(selected)
        provenance_index[field] = selected.provenance_id

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "state": state,
        "field_provenance_ids": provenance_index,
        "as_of": as_of,
    }
