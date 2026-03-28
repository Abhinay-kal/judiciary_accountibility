"""System status and integration readiness endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.ingestion.models import PopulationRun, IngestionSource
from app.models import Case, Hearing

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/integration-ready")
def check_integration_ready(db: Session = Depends(get_db)) -> dict:
    """Check if the system has data ready for the frontend to display.
    
    Returns:
        {
            "has_cases": bool,
            "has_population_run": bool,
            "active_sources": int,
            "total_cases": int,
            "total_hearings": int,
            "last_population_run": {
                "run_id": str,
                "status": str,
                "completed_sources": int,
                "records_processed": int
            } or null,
            "ready_for_interface": bool
        }
    """
    
    # Check case data
    total_cases = db.query(func.count(Case.id)).filter(Case.is_deleted.is_(False)).scalar() or 0
    total_hearings = db.query(func.count(Hearing.id)).filter(Hearing.is_deleted.is_(False)).scalar() or 0
    
    # Check active sources
    active_sources = db.query(func.count(IngestionSource.id)).filter(
        IngestionSource.is_active == True
    ).scalar() or 0
    
    # Check population run
    latest_population_run = db.query(PopulationRun).order_by(
        PopulationRun.created_at.desc()
    ).first()
    
    last_run_info = None
    if latest_population_run:
        last_run_info = {
            "run_id": latest_population_run.run_id,
            "status": latest_population_run.status,
            "completed_sources": latest_population_run.completed_sources or 0,
            "total_sources": latest_population_run.total_sources or 0,
            "records_processed": latest_population_run.records_processed or 0,
        }
    
    return {
        "has_cases": total_cases > 0,
        "has_population_run": latest_population_run is not None,
        "active_sources": active_sources,
        "total_cases": total_cases,
        "total_hearings": total_hearings,
        "last_population_run": last_run_info,
        "ready_for_interface": total_cases > 0 or active_sources >= 33,  # Ready if data exists OR all sources configured
    }
