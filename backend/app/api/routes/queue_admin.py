from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.celery_app import celery_app
from app.queue import QUEUE_NAMES
from app.queue.monitoring import QueueMonitor, collect_queue_status
from app.queue.workers import pipeline_signature, worker_profiles

router = APIRouter(prefix="/admin/queues", tags=["admin-queues"])


class TriggerTaskRequest(BaseModel):
    task_name: str = Field(min_length=3, max_length=120)
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)
    queue: str | None = None
    priority: int | None = Field(default=None, ge=1, le=9)


class TriggerPipelineRequest(BaseModel):
    source_id: int = Field(ge=1)
    job_id: str | None = Field(default=None, min_length=8, max_length=80)


_ALLOWED_MANUAL_TASKS = {
    "app.tasks.ingestion.run_daily_ingestion": "ingestion",
    "app.tasks.ingestion_tasks.run_ingestion_scheduler": "ingestion",
    "app.tasks.delay_analytics.run_delay_analytics_pipeline": "analytics",
    "app.tasks.survival_analytics.run_survival_pipeline": "analytics",
    "app.tasks.cache_tasks.refresh_precomputed_cache": "analytics",
}


@router.get("/status")
def queue_status() -> dict:
    statuses = collect_queue_status(celery_app, list(QUEUE_NAMES))
    return {
        "queues": [
            {
                "queue": item.queue,
                "depth": item.depth,
                "consumers": item.consumers,
                "paused": item.paused,
            }
            for item in statuses
        ],
        "worker_profiles": {
            queue: {
                "concurrency": profile.concurrency,
                "prefetch_multiplier": profile.prefetch_multiplier,
                "soft_time_limit": profile.soft_time_limit,
                "hard_time_limit": profile.hard_time_limit,
            }
            for queue, profile in worker_profiles().items()
        },
    }


@router.post("/ingestion/pause")
def pause_ingestion() -> dict:
    monitor = QueueMonitor(celery_app.conf.broker_url)
    monitor.set_ingestion_paused(True)
    return {"paused": True}


@router.post("/ingestion/resume")
def resume_ingestion() -> dict:
    monitor = QueueMonitor(celery_app.conf.broker_url)
    monitor.set_ingestion_paused(False)
    return {"paused": False}


@router.post("/jobs/trigger")
def trigger_manual_task(request: TriggerTaskRequest) -> dict:
    if request.task_name not in _ALLOWED_MANUAL_TASKS:
        raise HTTPException(status_code=400, detail="Task not permitted for manual trigger")

    queue = request.queue or _ALLOWED_MANUAL_TASKS[request.task_name]
    if queue not in QUEUE_NAMES:
        raise HTTPException(status_code=400, detail="Invalid queue")

    result = celery_app.send_task(
        request.task_name,
        args=request.args,
        kwargs=request.kwargs,
        queue=queue,
        priority=request.priority,
    )
    return {"task_id": result.id, "task_name": request.task_name, "queue": queue}


@router.post("/jobs/pipeline")
def trigger_pipeline(request: TriggerPipelineRequest) -> dict:
    job_id = request.job_id or str(uuid4())
    signature = pipeline_signature(source_id=request.source_id, job_id=job_id)
    result = signature.apply_async()
    return {"job_id": job_id, "root_task_id": result.id, "source_id": request.source_id}
