from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.models import (
    POPULATION_QUEUED,
    POPULATION_RUNNING,
    HEALTH_HEALTHY,
    HEALTH_DEGRADED,
    HEALTH_FAILED,
    HEALTH_DISABLED,
    PopulationRun,
    PopulationSourceRun,
    IngestionSource,
)
from app.models import Case, Hearing, Judge

router = APIRouter(prefix="/admin/data-overview", tags=["admin-data-overview"])


@router.get("/dashboard")
def get_dashboard_overview(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Get comprehensive dashboard statistics for admin overview."""
    
    # Get latest population run
    latest_run = (
        db.query(PopulationRun)
        .order_by(PopulationRun.created_at.desc())
        .first()
    )
    
    # Count sources by health status
    source_stats = {
        HEALTH_HEALTHY: db.query(func.count(IngestionSource.id)).filter(
            IngestionSource.health_status == HEALTH_HEALTHY
        ).scalar() or 0,
        HEALTH_DEGRADED: db.query(func.count(IngestionSource.id)).filter(
            IngestionSource.health_status == HEALTH_DEGRADED
        ).scalar() or 0,
        HEALTH_FAILED: db.query(func.count(IngestionSource.id)).filter(
            IngestionSource.health_status == HEALTH_FAILED
        ).scalar() or 0,
        HEALTH_DISABLED: db.query(func.count(IngestionSource.id)).filter(
            IngestionSource.health_status == HEALTH_DISABLED
        ).scalar() or 0,
    }
    
    # Get data counts
    total_cases = db.query(func.count(Case.id)).filter(Case.is_deleted.is_(False)).scalar() or 0
    total_hearings = db.query(func.count(Hearing.id)).filter(Hearing.is_deleted.is_(False)).scalar() or 0
    total_judges = db.query(func.count(Judge.id)).filter(Judge.is_deleted.is_(False)).scalar() or 0
    
    # Get recent sources
    recent_sources = (
        db.query(IngestionSource)
        .order_by(IngestionSource.last_success_at.desc())
        .limit(5)
        .all()
    )
    
    # Get active run status
    active_run = (
        db.query(PopulationRun)
        .filter(PopulationRun.status.in_([POPULATION_QUEUED, POPULATION_RUNNING]))
        .order_by(PopulationRun.created_at.desc())
        .first()
    )
    
    active_run_info = None
    if active_run:
        active_run_info = {
            "run_id": active_run.run_id,
            "status": active_run.status,
            "started_at": active_run.started_at.isoformat() if active_run.started_at else None,
            "total_sources": active_run.total_sources,
            "completed_sources": active_run.completed_sources,
            "successful_sources": active_run.successful_sources,
            "failed_sources": active_run.failed_sources,
            "records_processed": active_run.records_processed,
        }
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_run": active_run_info,
        "source_health": {
            "healthy": source_stats[HEALTH_HEALTHY],
            "degraded": source_stats[HEALTH_DEGRADED],
            "failed": source_stats[HEALTH_FAILED],
            "disabled": source_stats[HEALTH_DISABLED],
            "total": sum(source_stats.values()),
        },
        "data_counts": {
            "cases": total_cases,
            "hearings": total_hearings,
            "judges": total_judges,
        },
        "recent_sources": [
            {
                "id": src.id,
                "name": src.source_name,
                "health": src.health_status,
                "is_active": src.is_active,
                "last_success": src.last_success_at.isoformat() if src.last_success_at else None,
                "last_attempt": src.last_attempt_at.isoformat() if src.last_attempt_at else None,
                "failure_count": src.consecutive_failures,
            }
            for src in recent_sources
        ],
        "latest_run": {
            "run_id": latest_run.run_id if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "started_at": latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
            "records_processed": latest_run.records_processed if latest_run else 0,
        } if latest_run else None,
    }


@router.get("/latest-run")
def get_latest_run_details(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Get detailed statistics for the latest population run."""
    
    latest_run = (
        db.query(PopulationRun)
        .order_by(PopulationRun.created_at.desc())
        .first()
    )
    
    if not latest_run:
        return {"error": "No population runs found"}
    
    source_runs = (
        db.query(PopulationSourceRun)
        .filter(PopulationSourceRun.population_run_id == latest_run.id)
        .all()
    )
    
    status_breakdown = {}
    for sr in source_runs:
        status = sr.status if sr.status else "unknown"
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
    
    return {
        "run": {
            "run_id": latest_run.run_id,
            "trigger_type": latest_run.trigger_type,
            "status": latest_run.status,
            "admin_id": latest_run.admin_id,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            "total_sources": latest_run.total_sources,
            "completed_sources": latest_run.completed_sources,
            "successful_sources": latest_run.successful_sources,
            "failed_sources": latest_run.failed_sources,
            "records_processed": latest_run.records_processed,
            "records_failed": latest_run.records_failed,
        },
        "source_status_breakdown": status_breakdown,
        "sources": [
            {
                "source_id": sr.source_id,
                "source_name": sr.source_name,
                "status": sr.status,
                "records_processed": sr.records_processed,
                "records_failed": sr.records_failed,
                "error": sr.error_message or None,
            }
            for sr in sorted(source_runs, key=lambda x: x.id)
        ],
    }
