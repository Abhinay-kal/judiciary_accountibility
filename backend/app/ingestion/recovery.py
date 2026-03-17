"""Retry, checkpoint, and raw-payload reprocessing utilities.

Provides three independent capabilities:

1. **Exponential back-off sleep** (:func:`retry_with_backoff`) — used by
   the pipeline between fetch attempts.

2. **Checkpoint read/write** (:func:`save_checkpoint`,
   :func:`load_checkpoint`) — JSON files written to
   ``ingest_checkpoint_dir`` so that a crash in the middle of a large
   ingestion run can be resumed from the last safe position rather than
   restarting from scratch.

3. **Raw-payload reprocessing** (:func:`reprocess_raw_payload`) — given
   the ``run_id`` of a past run that stored a raw file, re-parse it with
   the *current* version of the parser and upsert the results.  Safe to
   call multiple times (idempotent at the database layer via existing
   upsert logic).

Usage::

    save_checkpoint(run_id="abc123", position={"page": 5, "offset": 200})
    position = load_checkpoint(run_id="abc123")

    reprocess_raw_payload(db, run_id="abc123")
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.models import IngestionRun, IngestionSource, RUN_SUCCESS, RUN_PARTIAL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exponential back-off
# ---------------------------------------------------------------------------


def retry_with_backoff(
    source_name: str,
    attempt: int,
    base_seconds: int = 60,
    max_seconds: int = 3600,
) -> None:
    """Sleep for ``base * 2^attempt`` seconds (capped at *max_seconds*).

    Parameters
    ----------
    source_name:
        Used in log messages only.
    attempt:
        Zero-based attempt index.  Attempt 0 has zero delay.
    base_seconds:
        Base delay multiplier (default: 60 seconds).
    max_seconds:
        Hard cap on sleep duration (default: 1 hour).
    """
    if attempt == 0:
        return
    delay = min(base_seconds * (2 ** (attempt - 1)), max_seconds)
    logger.info(
        "Source '%s' back-off: sleeping %ds before attempt %d.",
        source_name,
        delay,
        attempt,
    )
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Checkpoint persistence
# ---------------------------------------------------------------------------


def _checkpoint_path(run_id: str, checkpoint_dir: str) -> Path:
    return Path(checkpoint_dir) / f"{run_id}.checkpoint.json"


def save_checkpoint(
    run_id: str,
    position: dict[str, Any],
    settings: Optional[IngestionSettings] = None,
) -> None:
    """Persist *position* to a JSON checkpoint file.

    Parameters
    ----------
    run_id:
        Unique run identifier (UUID string).
    position:
        Arbitrary JSON-serialisable dict describing progress
        (e.g. ``{"page": 5, "offset": 200}``).
    settings:
        Defaults to ``get_ingestion_settings()``.
    """
    if settings is None:
        settings = get_ingestion_settings()
    path = _checkpoint_path(run_id, settings.ingest_checkpoint_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(position, default=str), encoding="utf-8")
    logger.debug("Checkpoint saved for run_id=%s at %s.", run_id, path)


def load_checkpoint(
    run_id: str,
    settings: Optional[IngestionSettings] = None,
) -> Optional[dict[str, Any]]:
    """Load a previously saved checkpoint.

    Returns
    -------
    dict or None
        The checkpoint dict, or ``None`` if no checkpoint file exists.
    """
    if settings is None:
        settings = get_ingestion_settings()
    path = _checkpoint_path(run_id, settings.ingest_checkpoint_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read checkpoint %s: %s", path, exc)
        return None


def delete_checkpoint(
    run_id: str,
    settings: Optional[IngestionSettings] = None,
) -> None:
    """Remove the checkpoint file after a successful run."""
    if settings is None:
        settings = get_ingestion_settings()
    path = _checkpoint_path(run_id, settings.ingest_checkpoint_dir)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete checkpoint %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Raw-payload reprocessing
# ---------------------------------------------------------------------------


def reprocess_raw_payload(
    db: Session,
    run_id: str,
) -> dict[str, Any]:
    """Re-parse a stored raw payload from a previous run.

    1. Looks up the :class:`~app.ingestion.models.IngestionRun` by
       *run_id*.
    2. Reads the raw bytes from ``run.raw_payload_location``.
    3. Looks up its :class:`~app.ingestion.models.IngestionSource`.
    4. Runs the pipeline's parse + upsert steps using the *current*
       parser version.
    5. Returns a summary dict with counts.

    This function is **idempotent** — the underlying upsert logic
    deduplicates records by ``case_id``.

    Raises
    ------
    LookupError
        If the run_id is not found in the database.
    FileNotFoundError
        If the raw payload file is missing from disk.
    """
    from app.ingestion.pipeline import ResilientIngestionPipeline  # noqa: PLC0415
    from app.services.normalization import (  # noqa: PLC0415
        normalize_case_record,
        upsert_case_from_normalized,
    )

    run: Optional[IngestionRun] = (
        db.query(IngestionRun).filter(IngestionRun.run_id == run_id).first()
    )
    if run is None:
        raise LookupError(f"IngestionRun with run_id='{run_id}' not found.")

    raw_path = run.raw_payload_location
    if not raw_path:
        raise FileNotFoundError(
            f"Run '{run_id}' has no raw_payload_location stored."
        )

    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"Raw payload file not found: {raw_path}")

    raw_content = path.read_bytes()

    source: Optional[IngestionSource] = db.get(IngestionSource, run.source_id)
    if source is None:
        raise LookupError(f"IngestionSource id={run.source_id} not found.")

    # Resolve scraper
    scraper_cls = ResilientIngestionPipeline._resolve_scraper(source)
    if scraper_cls is None:
        logger.warning(
            "No scraper registered for source '%s' — raw re-parse skipped.",
            source.source_name,
        )
        return {"status": "no_scraper", "inserted": 0, "failed": 0}

    from app.scrapers.base import ScrapeResult  # noqa: PLC0415

    scraper = scraper_cls()
    raw_result = ScrapeResult(
        source=source.source_name,
        url=source.base_url,
        content=raw_content,
        content_type="text/html",
        checksum="",
        raw_storage_path=raw_path,
    )

    inserted = 0
    failed = 0
    try:
        records = scraper.parse(raw_result) or []
    except Exception as exc:
        logger.error("Re-parse error for run '%s': %s", run_id, exc)
        return {"status": "parse_error", "error": str(exc), "inserted": 0, "failed": 0}

    for rec in records:
        try:
            normalized = normalize_case_record(rec)
            upsert_case_from_normalized(db, normalized)
            inserted += 1
        except Exception as exc:
            logger.error("Upsert error during reprocess of run '%s': %s", run_id, exc)
            failed += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Commit failed during reprocess of run '%s': %s", run_id, exc)
        return {"status": "commit_error", "error": str(exc), "inserted": 0, "failed": 0}

    logger.info(
        "Reprocessed run '%s': inserted=%d, failed=%d.", run_id, inserted, failed
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "source": source.source_name,
        "records_parsed": len(records),
        "inserted": inserted,
        "failed": failed,
    }
