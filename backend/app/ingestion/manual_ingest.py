from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.models import IngestionRun, IngestionSource, RUN_SUCCESS


def ingest_manual_payload(
    db: Session,
    *,
    source_id: int,
    payload: bytes,
    filename: str,
    media_type: str,
    case_id: Optional[str] = None,
    hearing_date: Optional[str] = None,
    settings: Optional[IngestionSettings] = None,
) -> IngestionRun:
    settings = settings or get_ingestion_settings()
    if not settings.manual_ingest_enabled:
        raise PermissionError("Manual ingest is disabled")

    source = db.get(IngestionSource, source_id)
    if not source:
        raise LookupError(f"Unknown source_id={source_id}")

    storage_dir = Path(settings.ingest_raw_storage_dir) / source.source_name / "manual"
    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    run_id = f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    file_path = storage_dir / f"{run_id}-{safe_name}"
    file_path.write_bytes(payload)

    run = IngestionRun(
        run_id=run_id,
        source_id=source_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=RUN_SUCCESS,
        raw_payload_location=str(file_path),
        records_fetched=1,
        records_parsed=1,
        records_inserted=1,
        records_failed=0,
        parser_version="manual-upload",
        provenance_json={
            "manual": True,
            "media_type": media_type,
            "case_id": case_id,
            "hearing_date": hearing_date,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(run)
    db.commit()
    return run


def generate_rti_template(*, source_name: str, blocked_reason: str, requester_name: str = "<REQUESTER_NAME>") -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return (
        "To,\n"
        "The Public Information Officer,\n"
        f"{source_name}\n\n"
        f"Date: {today}\n\n"
        "Subject: Request for access to public judicial data under RTI Act, 2005\n\n"
        f"Sir/Madam,\nI, {requester_name}, request machine-readable access to case listings/orders "
        f"currently unavailable via public channels.\n"
        f"Current access blocker: {blocked_reason}.\n"
        "Requested format: CSV/JSON/PDF index with document URLs and update timestamps.\n"
        "Purpose: public-interest judicial delay analytics and accountability dashboard.\n\n"
        "Please provide the requested information within statutory timelines.\n\n"
        "Sincerely,\n"
        f"{requester_name}\n"
    )
