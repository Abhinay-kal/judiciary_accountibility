from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.feedback_auth import is_admin_actor
from app.db.session import get_db
from app.ingestion.models import (
    POPULATION_QUEUED,
    POPULATION_RUNNING,
    PopulationRun,
    PopulationSourceRun,
)
from app.tasks.population import start_population_run

router = APIRouter(prefix="/admin/population", tags=["admin-population"])


class TriggerPopulationRequest(BaseModel):
    admin_id: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)
    priority: int | None = Field(default=6, ge=1, le=9)


@router.post("/runs/trigger", responses={422: {"description": "admin_id is required"}})
def trigger_population_run(
    request: TriggerPopulationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    if not is_admin_actor(request.admin_id):
        raise HTTPException(status_code=422, detail="admin_id is required")

    active = (
        db.query(PopulationRun)
        .filter(PopulationRun.status.in_([POPULATION_QUEUED, POPULATION_RUNNING]))
        .order_by(PopulationRun.started_at.desc())
        .first()
    )
    if active is not None:
        return {
            "status": "already_running",
            "run_id": active.run_id,
            "started_at": active.started_at,
        }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + str(uuid4())[:8]
    task = start_population_run.apply_async(
        kwargs={
            "run_id": run_id,
            "trigger_type": "MANUAL",
            "admin_id": request.admin_id,
            "reason": request.reason,
            "priority": request.priority,
        },
        queue="ingestion",
        priority=request.priority,
    )

    return {
        "status": "queued",
        "run_id": run_id,
        "task_id": task.id,
    }


@router.get("/runs")
def list_population_runs(
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    query = db.query(PopulationRun)
    if status:
        query = query.filter(PopulationRun.status == status.upper())
    total = query.count()
    runs = (
        query.order_by(PopulationRun.started_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "run_id": run.run_id,
                "trigger_type": run.trigger_type,
                "status": run.status,
                "admin_id": run.admin_id,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "total_sources": run.total_sources,
                "completed_sources": run.completed_sources,
                "successful_sources": run.successful_sources,
                "failed_sources": run.failed_sources,
                "records_processed": run.records_processed,
                "records_failed": run.records_failed,
                "reason": run.reason,
            }
            for run in runs
        ],
    }


@router.get("/runs/{run_id}", responses={404: {"description": "Population run not found"}})
def get_population_run(run_id: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    run = db.query(PopulationRun).filter(PopulationRun.run_id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Population run not found")

    source_runs = (
        db.query(PopulationSourceRun)
        .filter(PopulationSourceRun.population_run_id == run.id)
        .order_by(PopulationSourceRun.id.asc())
        .all()
    )
    return {
        "run": {
            "run_id": run.run_id,
            "trigger_type": run.trigger_type,
            "status": run.status,
            "admin_id": run.admin_id,
            "reason": run.reason,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "total_sources": run.total_sources,
            "completed_sources": run.completed_sources,
            "successful_sources": run.successful_sources,
            "failed_sources": run.failed_sources,
            "records_processed": run.records_processed,
            "records_failed": run.records_failed,
            "diagnostics": run.diagnostics,
        },
        "sources": [
            {
                "id": source_run.id,
                "source_id": source_run.source_id,
                "source_name": source_run.source_name,
                "status": source_run.status,
                "task_id": source_run.task_id,
                "records_processed": source_run.records_processed,
                "records_failed": source_run.records_failed,
                "error_summary": source_run.error_summary,
                "diagnostics": source_run.diagnostics,
                "started_at": source_run.started_at,
                "finished_at": source_run.finished_at,
            }
            for source_run in source_runs
        ],
    }
