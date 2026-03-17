from __future__ import annotations

from sqlalchemy.orm import Session

from app.provenance.models import FieldProvenance, ProvenanceLink


def trace_lineage_chain(db: Session, *, provenance_id: int) -> dict:
    """Return lineage graph from child provenance to all reachable ancestors."""

    nodes: dict[int, dict] = {}
    links: list[dict] = []
    visited: set[int] = set()
    queue = [provenance_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        item = db.query(FieldProvenance).filter(FieldProvenance.provenance_id == current).one_or_none()
        if item is None:
            continue

        nodes[current] = {
            "provenance_id": item.provenance_id,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "field_name": item.field_name,
            "field_value_hash": item.field_value_hash,
            "source_name": item.source_name,
            "source_type": item.source_type,
            "fetch_time": item.fetch_time,
            "confidence_score": item.confidence_score,
        }

        parent_links = (
            db.query(ProvenanceLink)
            .filter(ProvenanceLink.child_provenance_id == current)
            .all()
        )
        for link in parent_links:
            links.append(
                {
                    "parent_provenance_id": link.parent_provenance_id,
                    "child_provenance_id": link.child_provenance_id,
                    "relationship_type": link.relationship_type,
                }
            )
            queue.append(link.parent_provenance_id)

    return {
        "root_provenance_id": provenance_id,
        "nodes": list(nodes.values()),
        "links": links,
    }
