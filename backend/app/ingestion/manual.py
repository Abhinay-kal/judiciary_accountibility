"""Operator control tools for ingestion sources.

Provides four operator-facing actions:

* :func:`pause_source`        — set ``is_active=False``, health → DISABLED.
* :func:`resume_source`       — set ``is_active=True``, clear health.
* :func:`force_run`           — enqueue an immediate Celery run task.
* :func:`upload_manual_file`  — accept a raw bytes payload from an operator
  and create an :class:`~app.ingestion.models.IngestionRun` record manually.
* :func:`override_health`     — directly set the health status (operator
  escape-hatch; use sparingly).

All functions accept an open :class:`sqlalchemy.orm.Session` and commit
on success.  They raise :class:`LookupError` when the source_id is
unknown, and :class:`ValueError` for invalid inputs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.health import force_health_status, reset_source_health
from app.ingestion.models import (
    HEALTH_DISABLED,
    RUN_SUCCESS,
    IngestionRun,
    IngestionSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_source(db: Session, source_id: int) -> IngestionSource:
    source = db.get(IngestionSource, source_id)
    if source is None:
        raise LookupError(f"IngestionSource with id={source_id} not found.")
    return source


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------


def pause_source(db: Session, source_id: int) -> IngestionSource:
    """Disable a source so the scheduler skips it entirely.

    Sets ``is_active=False`` and health status to ``DISABLED``.
    """
    source = _get_source(db, source_id)
    source.is_active = False
    source.health_status = HEALTH_DISABLED
    db.commit()
    logger.warning("Operator paused source '%s' (id=%d).", source.source_name, source_id)
    return source


def resume_source(db: Session, source_id: int) -> IngestionSource:
    """Re-enable a paused source and reset its health to HEALTHY."""
    source = _get_source(db, source_id)
    source.is_active = True
    reset_source_health(source)
    db.commit()
    logger.info("Operator resumed source '%s' (id=%d).", source.source_name, source_id)
    return source


# ---------------------------------------------------------------------------
# Force run
# ---------------------------------------------------------------------------


def force_run(db: Session, source_id: int) -> str:
    """Enqueue an immediate Celery task for the given source.

    Returns the Celery task-id string.
    """
    source = _get_source(db, source_id)

    # Import here to avoid circular dependency at module load time
    from app.tasks.ingestion_tasks import run_single_source  # type: ignore[import]

    result = run_single_source.apply_async(args=[source_id], countdown=0)
    logger.info(
        "Operator force-run enqueued for source '%s', task_id=%s.",
        source.source_name,
        result.id,
    )
    return result.id


# ---------------------------------------------------------------------------
# Upload manual file
# ---------------------------------------------------------------------------


def upload_manual_file(
    db: Session,
    source_id: int,
    file_bytes: bytes,
    filename: str,
    settings: Optional[IngestionSettings] = None,
) -> IngestionRun:
    """Persist a raw file uploaded by an operator and create a run record.

    The file is written to ``{ingest_raw_storage_dir}/{source_name}/manual/``
    so it can later be reprocessed via :func:`~app.ingestion.recovery.reprocess_raw_payload`.

    Parameters
    ----------
    db:
        Open session.
    source_id:
        Target source id.
    file_bytes:
        Raw byte content of the uploaded file.
    filename:
        Original filename (used for storage path only).
    settings:
        Defaults to ``get_ingestion_settings()``.

    Returns
    -------
    IngestionRun
        The newly created run row, committed.
    """
    if settings is None:
        settings = get_ingestion_settings()

    source = _get_source(db, source_id)

    max_bytes = settings.ingest_max_raw_payload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(
            f"File size {len(file_bytes)} bytes exceeds limit "
            f"({settings.ingest_max_raw_payload_mb} MB)."
        )

    # Sanitise filename to prevent path traversal
    safe_name = Path(filename).name
    storage_dir = (
        Path(settings.ingest_raw_storage_dir) / source.source_name / "manual"
    )
    storage_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = storage_dir / f"{run_id}_{ts}_{safe_name}"
    dest.write_bytes(file_bytes)

    run = IngestionRun(
        run_id=run_id,
        source_id=source.id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status=RUN_SUCCESS,
        raw_payload_location=str(dest),
        records_fetched=0,
        records_parsed=0,
        records_inserted=0,
        records_failed=0,
        diagnostics={"upload": True, "original_filename": safe_name},
    )
    db.add(run)
    db.commit()
    logger.info(
        "Manual upload for source '%s' stored at %s (run_id=%s).",
        source.source_name,
        dest,
        run_id,
    )
    return run


# ---------------------------------------------------------------------------
# Health override
# ---------------------------------------------------------------------------


def override_health(db: Session, source_id: int, status: str) -> IngestionSource:
    """Manually set the health status of a source.

    Parameters
    ----------
    db:
        Open session.
    source_id:
        Target source id.
    status:
        One of ``HEALTHY``, ``DEGRADED``, ``FAILED``, ``DISABLED``.

    Raises
    ------
    ValueError
        If *status* is not a valid health constant.
    LookupError
        If no source with *source_id* exists.
    """
    source = _get_source(db, source_id)
    force_health_status(source, status)
    db.commit()
    return source
