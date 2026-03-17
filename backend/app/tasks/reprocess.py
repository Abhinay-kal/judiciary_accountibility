from __future__ import annotations

from dataclasses import dataclass

from app.celery_app import celery_app
from app.ingestion.parser_minimal import parse_minimal
from app.ingestion.models import IngestionRun, RawPayload
from app.storage.storage_client import StorageClient
from app.db.session import SessionLocal


@dataclass
class ReprocessSummary:
    parser_version: str
    scanned: int
    changed_estimate: int
    updated: int


def _reprocess_impl(parser_version: str, batch_size: int = 500, dry_run: bool = True) -> dict:
    db = SessionLocal()
    storage = StorageClient()
    scanned = 0
    changed = 0
    updated = 0
    try:
        rows = db.query(RawPayload).order_by(RawPayload.payload_id.asc()).limit(batch_size).all()
        for row in rows:
            scanned += 1
            payload = storage.get_bytes(row.storage_ref)
            result = parse_minimal(payload, row.media_type or "application/octet-stream")
            if result.parser_confidence > 0:
                changed += 1
            if dry_run:
                continue
            if row.ingestion_run_id is not None:
                run = db.get(IngestionRun, row.ingestion_run_id)
                if run is not None:
                    run.parser_version = parser_version
                    run.parser_confidence_score = result.parser_confidence
                    diag = dict(run.diagnostics or {})
                    history = list(diag.get("reprocess_history", []))
                    history.append(
                        {
                            "parser_version": parser_version,
                            "confidence": result.parser_confidence,
                            "errors": result.errors,
                        }
                    )
                    diag["reprocess_history"] = history
                    run.diagnostics = diag
                    updated += 1
        if not dry_run:
            db.commit()
        return {
            "parser_version": parser_version,
            "scanned": scanned,
            "changed_estimate": changed,
            "updated": updated,
            "dry_run": dry_run,
        }
    finally:
        db.close()


@celery_app.task(name="app.tasks.reprocess.reprocess_raw_snapshots")
def reprocess_raw_snapshots(parser_version: str, batch_size: int = 500, dry_run: bool = True) -> dict:
    return _reprocess_impl(parser_version=parser_version, batch_size=batch_size, dry_run=dry_run)
