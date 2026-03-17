from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Adjournment, Case, Court, Hearing, IngestionLog, Judge
from app.services.adjournment import detect_adjournment


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


def upsert_hearings_for_case(db: Session, case: Case, record: dict[str, Any], source: str) -> None:
    """Upsert hearing rows and derive adjournment signals from outcome text."""

    hearings = record.get("hearings") or []
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
                outcome_text=item.get("outcome_text"),
                source=source,
            )
            db.add(hearing)
            db.flush()

        is_adj, reason = detect_adjournment(item.get("outcome_text"))
        adjournment = (
            db.query(Adjournment)
            .filter(Adjournment.hearing_id == hearing.id, Adjournment.is_deleted.is_(False))
            .first()
        )
        if not adjournment:
            db.add(
                Adjournment(
                    case_id=case.id,
                    hearing_id=hearing.id,
                    is_adjournment=is_adj,
                    reason_category=reason,
                    source=source,
                )
            )
