from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingestion.hearing_outcomes import build_corroborating_signals, parse_outcome_text
from app.models import Hearing, JudgeAssignment, JudgeRegistry, Order


def build_hearing_evidence_bundle(db: Session, hearing: Hearing) -> dict:
    signals = build_corroborating_signals(
        db,
        case_id=hearing.case_id,
        hearing_date=hearing.date,
        current_source=hearing.source,
        existing_hearing=hearing,
    )
    parsed = parse_outcome_text(
        hearing.raw_outcome_text or hearing.outcome_text,
        listing_type=hearing.listing_type,
        source_name=hearing.source,
        parser_version=hearing.parser_version,
        has_order_pdf=any(signal.evidence_id and signal.evidence_id.startswith("order:") for signal in signals),
        corroborating_signals=signals,
        allow_ml=False,
    )
    orders = (
        db.query(Order)
        .filter(Order.case_id == hearing.case_id, Order.order_date == hearing.date, Order.is_deleted.is_(False))
        .all()
    )
    assignments = (
        db.query(JudgeAssignment)
        .filter(JudgeAssignment.hearing_id == hearing.id)
        .order_by(JudgeAssignment.sequence_index.asc())
        .all()
    )
    registry_map = {
        row.judge_id: row
        for row in db.query(JudgeRegistry).filter(
            JudgeRegistry.judge_id.in_([assignment.judge_id for assignment in assignments])
        )
    } if assignments else {}
    return {
        "raw_outcome_text": hearing.raw_outcome_text or hearing.outcome_text,
        "raw_bench": hearing.raw_bench,
        "parser_confidence": hearing.outcome_confidence,
        "source_links": [hearing.case.source_url] + [order.order_link for order in orders],
        "source_names": parsed.source_names,
        "matched_keywords": parsed.matched_keywords,
        "matched_rules": parsed.matched_rules,
        "corroborating_order_pdf": [
            {
                "order_id": order.id,
                "order_link": order.order_link,
                "source": order.source,
                "raw_reference": order.raw_reference,
            }
            for order in orders
        ],
        "cause_list_entry_link": hearing.case.source_url,
        "why": parsed.explanation,
        "needs_verification": parsed.needs_review,
        "judge_attribution": [
            {
                "assignment_id": assignment.assignment_id,
                "judge_id": assignment.judge_id,
                "canonical_name": registry_map.get(assignment.judge_id).canonical_name if assignment.judge_id in registry_map else None,
                "judge_name_raw": assignment.judge_name_raw,
                "role": assignment.role.value,
                "sequence_index": assignment.sequence_index,
                "is_presiding": assignment.is_presiding,
                "attribution_confidence": assignment.attribution_confidence,
                "match_type": assignment.matched_on,
                "tooltip_why": assignment.metadata_json,
                "needs_verification": assignment.attribution_confidence < 0.6,
            }
            for assignment in assignments
        ],
    }