from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.ingestion.models import (
    POPULATION_FAILED,
    POPULATION_PARTIAL,
    POPULATION_QUEUED,
    POPULATION_RUNNING,
    POPULATION_SUCCESS,
    IngestionSource,
    PopulationRun,
    PopulationSourceRun,
)
from app.queue import QUEUE_NAMES

logger = logging.getLogger(__name__)

_TERMINAL_STATES = {POPULATION_SUCCESS, POPULATION_PARTIAL, POPULATION_FAILED}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aggregate_population_run(db, run: PopulationRun) -> None:
    source_runs = (
        db.query(PopulationSourceRun)
        .filter(PopulationSourceRun.population_run_id == run.id)
        .all()
    )
    total = len(source_runs)
    completed = sum(1 for item in source_runs if item.status in _TERMINAL_STATES)
    successful = sum(1 for item in source_runs if item.status == POPULATION_SUCCESS)
    failed = sum(1 for item in source_runs if item.status == POPULATION_FAILED)
    processed = sum(item.records_processed for item in source_runs)
    failed_records = sum(item.records_failed for item in source_runs)

    run.total_sources = total
    run.completed_sources = completed
    run.successful_sources = successful
    run.failed_sources = failed
    run.records_processed = processed
    run.records_failed = failed_records

    if total == 0:
        run.status = POPULATION_SUCCESS
        run.finished_at = _utcnow()
        return

    if completed < total:
        run.status = POPULATION_RUNNING
        run.finished_at = None
        return

    if failed == 0:
        run.status = POPULATION_SUCCESS
    elif successful > 0:
        run.status = POPULATION_PARTIAL
    else:
        run.status = POPULATION_FAILED
    run.finished_at = _utcnow()


@celery_app.task(
    name="app.tasks.population.start_population_run",
    bind=True,
    max_retries=0,
)
def start_population_run(
    self,
    run_id: str | None = None,
    trigger_type: str = "MANUAL",
    admin_id: int | None = None,
    reason: str | None = None,
    queue: str = "ingestion",
    priority: int | None = 6,
) -> dict:
    db = SessionLocal()
    run_identifier = run_id or (datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + str(uuid4())[:8])
    try:
        active_run = (
            db.query(PopulationRun)
            .filter(PopulationRun.status.in_([POPULATION_QUEUED, POPULATION_RUNNING]))
            .order_by(PopulationRun.started_at.desc())
            .first()
        )
        if active_run is not None:
            return {
                "skipped": True,
                "reason": "active_run_exists",
                "active_run_id": active_run.run_id,
            }

        run = PopulationRun(
            run_id=run_identifier,
            trigger_type=trigger_type,
            status=POPULATION_RUNNING,
            admin_id=admin_id,
            reason=reason,
            root_task_id=getattr(self.request, "id", None),
            diagnostics={"trigger": trigger_type.lower()},
        )
        db.add(run)
        db.flush()

        sources = (
            db.query(IngestionSource)
            .filter(IngestionSource.is_active.is_(True))
            .order_by(IngestionSource.priority.asc(), IngestionSource.id.asc())
            .all()
        )

        source_runs: list[PopulationSourceRun] = []
        for source in sources:
            source_run = PopulationSourceRun(
                population_run_id=run.id,
                source_id=source.id,
                source_name=source.source_name,
                status=POPULATION_QUEUED,
            )
            db.add(source_run)
            source_runs.append(source_run)

        db.flush()

        target_queue = queue if queue in QUEUE_NAMES else "ingestion"
        for source_run in source_runs:
            task = run_population_source.apply_async(
                kwargs={
                    "population_run_id": run.id,
                    "source_run_id": source_run.id,
                    "source_id": source_run.source_id,
                },
                queue=target_queue,
                priority=priority,
            )
            source_run.task_id = task.id
            source_run.status = POPULATION_RUNNING

        _aggregate_population_run(db, run)
        db.commit()
        return {
            "run_id": run.run_id,
            "run_db_id": run.id,
            "source_runs": len(source_runs),
            "status": run.status,
        }
    except Exception:
        db.rollback()
        logger.exception("start_population_run failed")
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.population.run_population_source",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def run_population_source(
    self,
    population_run_id: int,
    source_run_id: int,
    source_id: int,
) -> dict:
    from app.ingestion.config import get_ingestion_settings
    from app.ingestion.pipeline import ResilientIngestionPipeline

    db = SessionLocal()
    try:
        source = db.get(IngestionSource, source_id)
        source_run = db.get(PopulationSourceRun, source_run_id)
        run = db.get(PopulationRun, population_run_id)

        if source is None or source_run is None or run is None:
            return {
                "error": "run/source record not found",
                "source_id": source_id,
                "population_run_id": population_run_id,
            }

        source_run.status = POPULATION_RUNNING
        source_run.started_at = source_run.started_at or _utcnow()
        db.flush()

        settings = get_ingestion_settings()
        pipeline = ResilientIngestionPipeline(db, settings)
        run_result = pipeline.run(source)

        source_run.records_processed = int(run_result.records_inserted or 0)
        source_run.records_failed = int(run_result.records_failed or 0)
        source_run.error_summary = run_result.error_summary
        source_run.diagnostics = {
            "ingestion_run_id": run_result.run_id,
            "ingestion_status": run_result.status,
        }
        source_run.status = POPULATION_SUCCESS if source_run.records_failed == 0 else POPULATION_PARTIAL
        source_run.finished_at = _utcnow()

        _aggregate_population_run(db, run)
        db.commit()

        return {
            "population_run_id": population_run_id,
            "source_run_id": source_run_id,
            "source_id": source_id,
            "status": source_run.status,
            "processed": source_run.records_processed,
            "failed": source_run.records_failed,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("run_population_source failed: source_id=%s", source_id)

        recovery_db = SessionLocal()
        try:
            source_run = recovery_db.get(PopulationSourceRun, source_run_id)
            run = recovery_db.get(PopulationRun, population_run_id)
            if source_run is not None:
                source_run.status = POPULATION_FAILED
                source_run.error_summary = str(exc)
                source_run.finished_at = _utcnow()
            if run is not None:
                _aggregate_population_run(recovery_db, run)
            recovery_db.commit()
        finally:
            recovery_db.close()
        raise
    finally:
        db.close()
