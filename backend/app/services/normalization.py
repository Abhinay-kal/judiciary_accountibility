from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.monitoring import JUDGE_ATTRIBUTION_LOW_CONFIDENCE_TOTAL, JUDGE_ATTRIBUTION_MISSING_TOTAL
from app.ingestion.hearing_outcomes import apply_outcome_to_hearing
from app.ingestion.models import IngestionSource
from app.models import Adjournment, Case, Court, Hearing, IngestionLog, Judge, JudgeAssignment, JudgeAttributionAudit
from app.services.adjournment import detect_adjournment
from app.services.judge_resolution import (
    build_assignments_from_bench,
    raw_bench_snapshot_id,
)

settings = get_settings()


def normalize_case_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize source records into unified case schema."""

    return {
        "case_uid": record["case_uid"],
        "cnr": record.get("cnr"),
        "case_number": record.get("case_number", "Unknown"),
        "court_name": record.get("court_name", "Unknown Court"),
        "court_level": record.get("court_level", "district"),
        "state": record.get("state", "Unknown"),
        "bench": record.get("bench"),
        "judges_text": record.get("judges_text"),
        "filing_date": record.get("filing_date"),
        "next_hearing_date": record.get("next_hearing_date"),
        "case_type": record.get("case_type"),
        "status": (record.get("status") or "pending").lower(),
        "source_url": record.get("source_url", ""),
        "source_fields": record.get("source_fields") or {},
        "last_source_updated_at": datetime.utcnow(),
    }


def upsert_case_from_normalized(db: Session, normalized: dict[str, Any]) -> Case:
    """Idempotent upsert for case records."""

    court = db.query(Court).filter(Court.name == normalized["court_name"], Court.is_deleted.is_(False)).first()
    if not court:
        court = Court(name=normalized["court_name"], level=normalized["court_level"], state=normalized["state"])
        db.add(court)
        db.flush()

    case = db.query(Case).filter(Case.case_uid == normalized["case_uid"], Case.is_deleted.is_(False)).first()
    if not case:
        case = Case(
            case_uid=normalized["case_uid"],
            cnr=normalized["cnr"],
            case_number=normalized["case_number"],
            court_id=court.id,
            court_level=normalized["court_level"],
            state=normalized["state"],
            bench=normalized["bench"],
            judges_text=normalized["judges_text"],
            filing_date=normalized["filing_date"],
            next_hearing_date=normalized["next_hearing_date"],
            case_type=normalized["case_type"],
            status=normalized["status"],
            source_url=normalized["source_url"],
            source_fields=normalized["source_fields"],
            last_source_updated_at=normalized["last_source_updated_at"],
        )
        db.add(case)
    else:
        case.case_number = normalized["case_number"]
        case.status = normalized["status"]
        case.next_hearing_date = normalized["next_hearing_date"]
        case.source_url = normalized["source_url"]
        case.source_fields = normalized["source_fields"]
        case.last_source_updated_at = normalized["last_source_updated_at"]

    db.flush()

    if settings.importance_fastpass_enabled:
        from app.services.importance import CaseImportanceScorer

        CaseImportanceScorer(db).score_and_persist_case(case, fast_pass=True)

    return case


def create_ingestion_log(
    db: Session,
    *,
    source: str,
    run_id: str,
    source_url: str | None,
    status: str,
    raw_storage_path: str | None,
    checksum: str | None,
    error_message: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    """Create an ingestion log entry."""

    db.add(
        IngestionLog(
            source=source,
            run_id=run_id,
            source_url=source_url,
            status=status,
            raw_storage_path=raw_storage_path,
            checksum=checksum,
            error_message=error_message,
            metadata_json=metadata_json or {},
        )
    )
    db.flush()


def upsert_hearings_for_case(
    db: Session,
    case: Case,
    record: dict[str, Any],
    source: str,
    *,
    ingestion_run_id: str | None = None,
) -> None:
    """Upsert hearing rows and derive adjournment signals from outcome text."""

    hearings = record.get("hearings") or []
    source_row = db.query(IngestionSource).filter(IngestionSource.source_name == source).one_or_none()
    source_id = source_row.id if source_row else None
    for item in hearings:
        hearing_date = item.get("date")
        if not hearing_date:
            continue

        judge_id = None
        judge_name = item.get("judge")
        if judge_name:
            judge = db.query(Judge).filter(Judge.name == judge_name, Judge.is_deleted.is_(False)).first()
            if not judge:
                judge = Judge(name=judge_name, court_id=case.court_id)
                db.add(judge)
                db.flush()
            judge_id = judge.id

        hearing = (
            db.query(Hearing)
            .filter(Hearing.case_id == case.id, Hearing.date == hearing_date, Hearing.is_deleted.is_(False))
            .first()
        )
        if not hearing:
            hearing = Hearing(
                case_id=case.id,
                date=hearing_date,
                judge_id=judge_id,
                listing_type=item.get("listing_type"),
                raw_bench=item.get("raw_bench") or item.get("bench") or item.get("coram"),
                outcome_text=item.get("outcome_text") or item.get("raw_outcome_text"),
                source=source,
            )
            db.add(hearing)
            db.flush()
        else:
            hearing.judge_id = judge_id
            hearing.listing_type = item.get("listing_type")
            hearing.raw_bench = item.get("raw_bench") or item.get("bench") or item.get("coram") or hearing.raw_bench
            hearing.outcome_text = item.get("outcome_text") or item.get("raw_outcome_text")
            hearing.source = source

        parse_result = apply_outcome_to_hearing(
            db,
            hearing,
            raw_outcome_text=item.get("raw_outcome_text") or item.get("outcome_text"),
            listing_type=item.get("listing_type"),
            source_name=source,
            parser_version=item.get("parser_version") or settings.outcome_parser_version,
        )

        is_adj, reason = detect_adjournment(
            item.get("raw_outcome_text") or item.get("outcome_text"),
            parsed_outcome=parse_result.outcome_type,
        )
        adjournment = (
            db.query(Adjournment)
            .filter(Adjournment.hearing_id == hearing.id, Adjournment.is_deleted.is_(False))
            .first()
        )
        if not adjournment:
            adjournment = Adjournment(
                case_id=case.id,
                hearing_id=hearing.id,
                is_adjournment=is_adj,
                reason_category=reason,
                source=source,
            )
            db.add(adjournment)
        else:
            adjournment.is_adjournment = is_adj
            adjournment.reason_category = reason
            adjournment.source = source

        assignment_payloads = build_assignments_from_bench(
            db,
            raw_bench=hearing.raw_bench,
            court_id=case.court_id,
            source_name=source,
            hearing_date=hearing.date,
        )
        snapshot_id = raw_bench_snapshot_id(hearing.raw_bench)
        if not assignment_payloads:
            JUDGE_ATTRIBUTION_MISSING_TOTAL.labels(source=source).inc()
        for payload in assignment_payloads:
            if payload.attribution_confidence < settings.judge_match_confidence_threshold:
                JUDGE_ATTRIBUTION_LOW_CONFIDENCE_TOTAL.labels(source=source).inc()
            existing_assignment = (
                db.query(JudgeAssignment)
                .filter(
                    JudgeAssignment.hearing_id == hearing.id,
                    JudgeAssignment.judge_id == payload.judge_registry_id,
                    JudgeAssignment.sequence_index == payload.sequence_index,
                )
                .one_or_none()
            )
            if existing_assignment is None:
                assignment = JudgeAssignment(
                    hearing_id=hearing.id,
                    judge_id=payload.judge_registry_id,
                    judge_name_raw=payload.judge_name_raw,
                    role=payload.role,
                    is_presiding=payload.is_presiding,
                    sequence_index=payload.sequence_index,
                    attribution_confidence=payload.attribution_confidence,
                    matched_on=payload.matched_on,
                    source_id=source_id,
                    ingestion_run_id=ingestion_run_id,
                    raw_bench_snapshot_id=snapshot_id,
                    parser_version=settings.outcome_parser_version,
                    metadata_json=payload.metadata_json,
                )
                db.add(assignment)
                db.flush()
                db.add(
                    JudgeAttributionAudit(
                        action="auto_assign",
                        hearing_id=hearing.id,
                        assignment_id=assignment.assignment_id,
                        judge_registry_id=assignment.judge_id,
                        reason="Automatic bench attribution during ingestion",
                        old_value={},
                        new_value={
                            "judge_name_raw": assignment.judge_name_raw,
                            "role": assignment.role.value,
                            "confidence": assignment.attribution_confidence,
                            "matched_on": assignment.matched_on,
                        },
                    )
                )
            else:
                old_value = {
                    "judge_name_raw": existing_assignment.judge_name_raw,
                    "role": existing_assignment.role.value,
                    "confidence": existing_assignment.attribution_confidence,
                    "matched_on": existing_assignment.matched_on,
                }
                existing_assignment.judge_name_raw = payload.judge_name_raw
                existing_assignment.role = payload.role
                existing_assignment.is_presiding = payload.is_presiding
                existing_assignment.attribution_confidence = payload.attribution_confidence
                existing_assignment.matched_on = payload.matched_on
                existing_assignment.source_id = source_id
                existing_assignment.ingestion_run_id = ingestion_run_id
                existing_assignment.raw_bench_snapshot_id = snapshot_id
                existing_assignment.parser_version = settings.outcome_parser_version
                existing_assignment.metadata_json = payload.metadata_json
                db.add(
                    JudgeAttributionAudit(
                        action="auto_assign_update",
                        hearing_id=hearing.id,
                        assignment_id=existing_assignment.assignment_id,
                        judge_registry_id=existing_assignment.judge_id,
                        reason="Automatic bench attribution update during ingestion",
                        old_value=old_value,
                        new_value={
                            "judge_name_raw": existing_assignment.judge_name_raw,
                            "role": existing_assignment.role.value,
                            "confidence": existing_assignment.attribution_confidence,
                            "matched_on": existing_assignment.matched_on,
                        },
                    )
                )
    db.flush()
