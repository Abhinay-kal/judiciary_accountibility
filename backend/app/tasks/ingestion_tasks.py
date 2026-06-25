"""Celery tasks for the resilient ingestion module.

Tasks
-----
* :func:`run_single_source` — run the full 10-step pipeline for one
  :class:`~app.ingestion.models.IngestionSource` identified by *source_id*.
* :func:`run_ingestion_scheduler` — periodic task that calls
  :func:`~app.ingestion.scheduler.schedule_due_sources` to dispatch
  individual source tasks.
* :func:`run_monitor_sweep_task` — periodic task that executes the
  monitor sweep and fires alerts.
"""
from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.queue.monitoring import QueueMonitor, apply_ingestion_backpressure

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ingestion_tasks.run_single_source",
    bind=True,
    max_retries=0,  # retries are handled inside ResilientIngestionPipeline
    acks_late=True,
)
def run_single_source(self, source_id: int) -> dict:
    """Execute the full ingestion pipeline for one source.

    Parameters
    ----------
    source_id:
        Primary key of the :class:`~app.ingestion.models.IngestionSource`.
    """
    from app.ingestion.config import get_ingestion_settings
    from app.ingestion.models import IngestionSource
    from app.ingestion.pipeline import ResilientIngestionPipeline

    db = SessionLocal()
    try:
        source = db.get(IngestionSource, source_id)
        if source is None:
            logger.error("run_single_source: source_id=%d not found.", source_id)
            return {"error": f"source_id={source_id} not found"}

        settings = get_ingestion_settings()
        pipeline = ResilientIngestionPipeline(db, settings)
        run = pipeline.run(source)
        return {
            "run_id": run.run_id,
            "source": source.source_name,
            "status": run.status,
            "inserted": run.records_inserted,
            "failed": run.records_failed,
        }
    except Exception as exc:
        logger.exception(
            "Unhandled error in run_single_source(source_id=%d): %s",
            source_id,
            exc,
        )
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.ingestion_tasks.run_ingestion_scheduler",
    bind=True,
    max_retries=0,
)
def run_ingestion_scheduler(self) -> dict:
    """Sweep all active sources and dispatch tasks for those that are due."""
    from app.ingestion.scheduler import schedule_due_sources

    settings = get_settings()
    monitor = QueueMonitor(settings.celery_broker_url)
    if apply_ingestion_backpressure(celery_app, max_depth=settings.ingestion_queue_max_depth):
        return {"dispatched_source_ids": [], "count": 0, "paused": True, "reason": "backpressure"}

    if monitor.is_ingestion_paused():
        return {"dispatched_source_ids": [], "count": 0, "paused": True, "reason": "manual_pause"}

    db = SessionLocal()
    try:
        dispatched = schedule_due_sources(db)
        return {"dispatched_source_ids": dispatched, "count": len(dispatched), "paused": False}
    except Exception as exc:
        logger.exception("Unhandled error in run_ingestion_scheduler: %s", exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.ingestion_tasks.run_monitor_sweep_task",
    bind=True,
    max_retries=0,
)
def run_monitor_sweep_task(self) -> dict:
    """Run the cross-source monitoring sweep and dispatch alerts."""
    from app.ingestion.monitor import run_monitor_sweep

    db = SessionLocal()
    try:
        fired = run_monitor_sweep(db)
        return {"alerts_fired": fired, "sources_alerted": len(fired)}
    except Exception as exc:
        logger.exception("Unhandled error in run_monitor_sweep_task: %s", exc)
        raise
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.ingestion_tasks.run_deferred_batch_jobs",
    bind=True,
    max_retries=0,
)
def run_deferred_batch_jobs(self, batch_size: int = 500) -> dict:
    """Run heavy NLP/indexing jobs outside ingestion hot path."""
    from app.ingestion.batch_jobs import DeferredBatchJobs

    db = SessionLocal()
    try:
        jobs = DeferredBatchJobs(db)
        text_index = jobs.build_text_index(batch_size=batch_size)
        enrichment = jobs.run_nlp_enrichment(batch_size=batch_size)
        return {"text_index": text_index, "nlp_enrichment": enrichment}
    finally:
        db.close()
