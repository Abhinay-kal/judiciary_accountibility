"""
Analytics API routes for case statistics and analysis.
Provides endpoints for comprehensive case data analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.case_analysis import CaseAnalysisService

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


@router.get("/cases/summary")
def get_case_summary(db: Session = Depends(get_db)):
    """Get comprehensive case statistics summary."""
    service = CaseAnalysisService(db)
    return service.get_case_statistics_summary()


@router.get("/cases/by-court")
def get_cases_by_court(db: Session = Depends(get_db)):
    """Get case counts broken down by court."""
    service = CaseAnalysisService(db)
    return service.get_case_count_by_court()


@router.get("/cases/by-state")
def get_cases_by_state(db: Session = Depends(get_db)):
    """Get case counts broken down by state."""
    service = CaseAnalysisService(db)
    return service.get_case_count_by_state()


@router.get("/cases/by-type")
def get_cases_by_type(db: Session = Depends(get_db)):
    """Get case counts broken down by case type."""
    service = CaseAnalysisService(db)
    return service.get_case_count_by_type()


@router.get("/cases/disposal-status")
def get_disposal_status(db: Session = Depends(get_db)):
    """Get distribution of cases by disposal status."""
    service = CaseAnalysisService(db)
    return {
        "disposal_distribution": service.get_disposal_status_distribution(),
        "pending_vs_disposed": service.get_pending_vs_disposed()
    }


@router.get("/cases/distribution/court-type")
def get_court_type_distribution(db: Session = Depends(get_db)):
    """Get case distribution across courts and case types."""
    service = CaseAnalysisService(db)
    return service.get_case_distribution_court_type()


@router.get("/cases/distribution/state-type")
def get_state_type_distribution(db: Session = Depends(get_db)):
    """Get case distribution across states and case types."""
    service = CaseAnalysisService(db)
    return service.get_case_distribution_state_type()


@router.get("/courts/performance")
def get_court_performance(db: Session = Depends(get_db)):
    """Get performance overview for each court (disposal rates, pending cases, etc)."""
    service = CaseAnalysisService(db)
    return {
        "courts": service.get_court_performance_overview()
    }


@router.get("/cases/trend/12-months")
def get_12month_trend(db: Session = Depends(get_db)):
    """Get 12-month trend of cases filed."""
    service = CaseAnalysisService(db)
    return service.get_cases_trend_12_months()


@router.get("/cases/by-date-range")
def get_cases_by_date_range(
    start_date: str = Query(..., description="Start date (ISO format: YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (ISO format: YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Get case counts for a specific date range."""
    service = CaseAnalysisService(db)
    return service.get_cases_filed_by_date_range(start_date, end_date)


@router.get("/cases/by-filing-month")
def get_cases_by_filing_month(
    months_back: int = Query(12, ge=1, le=60, description="Number of months to look back"),
    db: Session = Depends(get_db)
):
    """Get case count by filing month for the last N months."""
    service = CaseAnalysisService(db)
    return service.get_cases_by_filing_month(months_back)


@router.get("/hearings/outcomes")
def get_hearing_outcomes(db: Session = Depends(get_db)):
    """Get hearing outcomes distribution and adjournment rate."""
    service = CaseAnalysisService(db)
    return {
        "outcomes_distribution": service.get_hearing_outcomes_distribution(),
        "adjournment_rate": service.get_adjournment_rate()
    }
