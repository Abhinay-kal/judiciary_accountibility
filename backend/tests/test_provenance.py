from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.provenance.conflict import find_field_conflicts
from app.provenance.lineage import trace_lineage_chain
from app.provenance.models import FieldProvenance, ProvenanceLink
from app.provenance.queries import get_field_provenance
from app.provenance.recorder import record_derived_field_provenance, record_field_provenance
from app.provenance.reconstruction import reconstruct_entity_state


def _db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    FieldProvenance.__table__.create(bind=engine)
    ProvenanceLink.__table__.create(bind=engine)
    Local = sessionmaker(bind=engine, class_=Session)
    return Local()


def test_multi_source_fields_are_preserved():
    db = _db()
    try:
        record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="101",
            field_name="filing_date",
            value="2020-01-01",
            source_name="high_court_api",
            source_type="API",
            confidence_score=0.95,
        )
        record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="101",
            field_name="filing_date",
            value="2020-01-02",
            source_name="cause_list_html",
            source_type="HTML",
            confidence_score=0.72,
        )
        db.commit()

        rows = get_field_provenance(db, entity_type="CASE", entity_id="101", field_name="filing_date")
        assert len(rows) == 2
        assert {row.source_name for row in rows} == {"high_court_api", "cause_list_html"}
    finally:
        db.close()


def test_conflict_detection_links_mismatched_values():
    db = _db()
    try:
        first = record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="102",
            field_name="filing_date",
            value="2020-01-01",
            source_name="api_a",
            source_type="API",
            confidence_score=0.9,
        )
        second = record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="102",
            field_name="filing_date",
            value="2021-05-07",
            source_name="api_b",
            source_type="API",
            confidence_score=0.91,
        )
        db.commit()

        conflicts = find_field_conflicts(db, entity_type="CASE", entity_id="102", field_name="filing_date")
        assert len(conflicts) == 2

        links = db.query(ProvenanceLink).all()
        assert len(links) >= 1
        assert any(link.parent_provenance_id == second.provenance_id and link.child_provenance_id == first.provenance_id for link in links)
    finally:
        db.close()


def test_derived_lineage_is_traceable():
    db = _db()
    try:
        filing = record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="103",
            field_name="filing_date",
            value="2010-01-01",
            source_name="api_main",
            source_type="API",
            confidence_score=0.95,
        )
        disposal = record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="103",
            field_name="disposal_date",
            value="2015-01-01",
            source_name="api_main",
            source_type="API",
            confidence_score=0.94,
        )
        derived = record_derived_field_provenance(
            db,
            entity_type="CASE",
            entity_id="103",
            field_name="delay_days",
            derived_value=1826,
            parent_provenance_ids=[filing.provenance_id, disposal.provenance_id],
            transformation_steps=[{"step": "difference_days", "output_value": 1826}],
        )
        db.commit()

        chain = trace_lineage_chain(db, provenance_id=derived.provenance_id)
        assert chain["root_provenance_id"] == derived.provenance_id
        assert len(chain["links"]) == 2
        assert len(chain["nodes"]) >= 3
    finally:
        db.close()


def test_reconstruction_prefers_primary_and_confidence():
    db = _db()
    try:
        record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="104",
            field_name="status",
            value="PENDING",
            source_name="older_feed",
            source_type="HTML",
            confidence_score=0.4,
            transformation_steps=[{"step": "capture", "output_value": "PENDING"}],
            mark_primary=False,
        )
        record_field_provenance(
            db,
            entity_type="CASE",
            entity_id="104",
            field_name="status",
            value="DISPOSED",
            source_name="official_api",
            source_type="API",
            confidence_score=0.96,
            transformation_steps=[{"step": "capture", "output_value": "DISPOSED"}],
            mark_primary=True,
        )
        db.commit()

        state = reconstruct_entity_state(db, entity_type="CASE", entity_id="104")
        assert state["state"]["status"] == "DISPOSED"
    finally:
        db.close()


def test_missing_sources_return_empty_reconstruction():
    db = _db()
    try:
        rows = get_field_provenance(db, entity_type="CASE", entity_id="404", field_name="filing_date")
        assert rows == []
        state = reconstruct_entity_state(db, entity_type="CASE", entity_id="404")
        assert state["state"] == {}
    finally:
        db.close()
