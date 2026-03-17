"""REST API routes for the Resilient Ingestion module.

All endpoints require a valid DB session via the ``get_db`` dependency.
No authentication middleware is wired here — integrate with your existing
auth layer at the router-include site in ``app/api/router.py``.

Endpoints
---------
GET  /ingestion/sources                    — list all sources with health
GET  /ingestion/sources/{id}/health        — detailed health for one source
GET  /ingestion/runs                       — paginated run log
POST /ingestion/sources/{id}/pause         — pause a source
POST /ingestion/sources/{id}/resume        — resume a paused source
POST /ingestion/sources/{id}/run           — force immediate run
POST /ingestion/manual-upload              — file upload (multipart)
POST /ingestion/runs/{run_id}/reprocess    — re-parse a stored raw payload
PUT  /ingestion/sources/{id}/health-override — override health status
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.manual import (
    force_run,
    override_health,
    pause_source,
    resume_source,
    upload_manual_file,
)
from app.ingestion.manual_ingest import generate_rti_template, ingest_manual_payload
from app.ingestion.models import (
    HEALTH_DEGRADED,
    HEALTH_DISABLED,
    HEALTH_FAILED,
    HEALTH_HEALTHY,
    IngestionRun,
    IngestionSource,
    RawPayload,
)
from app.ingestion.recovery import reprocess_raw_payload
from app.ingestion.lifecycle import LifecycleManager, LifecyclePolicy
from app.storage.storage_client import StorageClient

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

_VALID_HEALTH_STATUSES = {HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_FAILED, HEALTH_DISABLED}


# ---------------------------------------------------------------------------
# GET /ingestion/sources
# ---------------------------------------------------------------------------


@router.get("/sources", summary="List all ingestion sources with health status")
def list_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return all registered ingestion sources with their current health."""
    sources: list[IngestionSource] = db.query(IngestionSource).order_by(
        IngestionSource.priority.asc()
    ).all()
    return [_source_summary(s) for s in sources]


# ---------------------------------------------------------------------------
# GET /ingestion/sources/{id}/health
# ---------------------------------------------------------------------------


@router.get(
    "/sources/{source_id}/health",
    summary="Detailed health info for a single source",
)
def get_source_health(
    source_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return detailed health information for a single ingestion source."""
    source = _get_source_or_404(db, source_id)
    last_run: Optional[IngestionRun] = (
        db.query(IngestionRun)
        .filter(IngestionRun.source_id == source_id)
        .order_by(IngestionRun.started_at.desc())
        .first()
    )
    result = _source_summary(source)
    result["last_run"] = _run_summary(last_run) if last_run else None
    return result


# ---------------------------------------------------------------------------
# GET /ingestion/runs
# ---------------------------------------------------------------------------


@router.get("/runs", summary="Paginated ingestion run log")
def list_runs(
    source_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return a paginated list of ingestion run records.

    Parameters
    ----------
    source_id:
        Optional filter — if provided, returns only runs for that source.
    limit:
        Page size (max 200).
    offset:
        Pagination offset.
    """
    limit = min(limit, 200)
    query = db.query(IngestionRun)
    if source_id is not None:
        query = query.filter(IngestionRun.source_id == source_id)
    total = query.count()
    runs = (
        query.order_by(IngestionRun.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_run_summary(r) for r in runs],
    }


# ---------------------------------------------------------------------------
# POST /ingestion/sources/{id}/pause
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/pause",
    status_code=status.HTTP_200_OK,
    summary="Pause a source (stops scheduler from dispatching runs)",
)
def pause(source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        source = pause_source(db, source_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": f"Source '{source.source_name}' paused.", "health": source.health_status}


# ---------------------------------------------------------------------------
# POST /ingestion/sources/{id}/resume
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/resume",
    status_code=status.HTTP_200_OK,
    summary="Resume a paused source",
)
def resume(source_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        source = resume_source(db, source_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": f"Source '{source.source_name}' resumed.", "health": source.health_status}


# ---------------------------------------------------------------------------
# POST /ingestion/sources/{id}/run
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Force an immediate ingestion run for a source",
)
def force_run_endpoint(
    source_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        task_id = force_run(db, source_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery task module not available.",
        )
    return {"task_id": task_id, "message": "Run enqueued."}


# ---------------------------------------------------------------------------
# POST /ingestion/manual-upload
# ---------------------------------------------------------------------------


@router.post(
    "/manual-upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a raw data file for a source (operator tool)",
)
async def manual_upload(
    source_id: int = Form(...),
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    hearing_date: Optional[str] = Form(None),
    media_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Accept a raw file upload from an operator.

    The file is stored in ``raw_data/{source_name}/manual/`` and a new
    ``IngestionRun`` record is created so it appears in the audit log.
    """
    file_bytes = await file.read()
    filename = file.filename or "upload.bin"

    # Validate filename to prevent path traversal
    from pathlib import Path as _Path
    safe_filename = _Path(filename).name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    try:
        run = ingest_manual_payload(
            db,
            source_id=source_id,
            payload=file_bytes,
            filename=safe_filename,
            media_type=media_type or (file.content_type or "application/octet-stream"),
            case_id=case_id,
            hearing_date=hearing_date,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "run_id": run.run_id,
        "raw_payload_location": run.raw_payload_location,
        "message": "File uploaded and run record created.",
    }


@router.get(
    "/sources/{source_id}/rti-template",
    summary="Generate RTI request template for blocked source",
)
def rti_template(
    source_id: int,
    blocked_reason: str,
    requester_name: str = "<REQUESTER_NAME>",
    db: Session = Depends(get_db),
) -> dict[str, str]:
    source = _get_source_or_404(db, source_id)
    return {
        "source_name": source.source_name,
        "template": generate_rti_template(
            source_name=source.source_name,
            blocked_reason=blocked_reason,
            requester_name=requester_name,
        ),
    }


@router.post("/lifecycle/apply", summary="Apply lifecycle tier rules to recent raw payload objects")
def apply_lifecycle(limit: int = 500, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = (
        db.query(RawPayload)
        .order_by(RawPayload.retrieved_at.desc())
        .limit(max(1, min(limit, 5000)))
        .all()
    )
    keys = [row.storage_ref for row in rows]
    manager = LifecycleManager(StorageClient(), LifecyclePolicy())
    moved = manager.apply_rules(keys)
    return {"scanned": len(keys), "moved": moved}


@router.post("/lifecycle/restore", summary="Restore archived object to hot tier")
def restore_lifecycle_object(checksum: str, db: Session = Depends(get_db)) -> dict[str, str]:
    row = db.query(RawPayload).filter(RawPayload.checksum == checksum).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No raw payload found for checksum={checksum}")
    manager = LifecycleManager(StorageClient(), LifecyclePolicy())
    manager.restore_archived(row.storage_ref)
    return {"checksum": checksum, "storage_ref": row.storage_ref, "status": "restored"}


# ---------------------------------------------------------------------------
# POST /ingestion/runs/{run_id}/reprocess
# ---------------------------------------------------------------------------


@router.post(
    "/runs/{run_id}/reprocess",
    status_code=status.HTTP_200_OK,
    summary="Re-parse and re-upsert a stored raw payload",
)
def reprocess(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Re-process a stored raw payload using the current parser version.

    Safe to call multiple times (idempotent upsert).
    """
    try:
        result = reprocess_raw_payload(db, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# ---------------------------------------------------------------------------
# PUT /ingestion/sources/{id}/health-override
# ---------------------------------------------------------------------------


@router.put(
    "/sources/{source_id}/health-override",
    status_code=status.HTTP_200_OK,
    summary="Manually override source health status (operator escape-hatch)",
)
def health_override(
    source_id: int,
    body: dict[str, str],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Set the health status of a source directly.

    Request body::

        {"status": "HEALTHY"}

    Valid values: ``HEALTHY``, ``DEGRADED``, ``FAILED``, ``DISABLED``.
    """
    new_status = (body.get("status") or "").upper()
    if new_status not in _VALID_HEALTH_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{new_status}'. Valid: {sorted(_VALID_HEALTH_STATUSES)}",
        )
    try:
        source = override_health(db, source_id, new_status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "source_id": source_id,
        "source_name": source.source_name,
        "health_status": source.health_status,
        "message": "Health status overridden.",
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_source_or_404(db: Session, source_id: int) -> IngestionSource:
    source = db.get(IngestionSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source id={source_id} not found.")
    return source


def _source_summary(source: IngestionSource) -> dict[str, Any]:
    return {
        "id": source.id,
        "source_name": source.source_name,
        "source_type": source.source_type,
        "base_url": source.base_url,
        "is_active": source.is_active,
        "health_status": source.health_status,
        "priority": source.priority,
        "consecutive_failures": source.consecutive_failures,
        "failure_count": source.failure_count,
        "last_success_at": source.last_success_at,
        "last_attempt_at": source.last_attempt_at,
        "last_error": source.last_error,
        "last_http_status": source.last_http_status,
        "last_record_count": source.last_record_count,
        "parser_version": source.parser_version,
    }


def _run_summary(run: IngestionRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "source_id": run.source_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "records_fetched": run.records_fetched,
        "records_inserted": run.records_inserted,
        "records_failed": run.records_failed,
        "http_status": run.http_status,
        "parser_confidence_score": run.parser_confidence_score,
        "schema_change_detected": run.schema_change_detected,
        "volume_anomaly_detected": run.volume_anomaly_detected,
        "error_summary": run.error_summary,
        "raw_payload_location": run.raw_payload_location,
    }
