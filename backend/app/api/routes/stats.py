from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Court, Judge
from app.schemas.stats import CourtStatsOut
from app.services.metrics import backlog_indicators, judge_adjournment_rate

router = APIRouter(prefix="/stats")


@router.get("/court", response_model=list[CourtStatsOut])
def get_court_stats(db: Session = Depends(get_db)):
    indicators = backlog_indicators(db)
    output = []
    for row in indicators:
        court = db.query(Court).filter(Court.id == row["court_id"], Court.is_deleted.is_(False)).first()
        if not court:
            continue
        output.append(
            CourtStatsOut(
                court_id=court.id,
                court_name=court.name,
                total_cases=row["total_cases"],
                pending_cases=row["pending_cases"],
                disposed_cases=row["disposed_cases"],
                backlog_ratio=row["backlog_ratio"],
            )
        )
    return output


@router.get("/judge")
def get_judge_stats_summary(db: Session = Depends(get_db)):
    judges = db.query(Judge).filter(Judge.is_deleted.is_(False)).all()
    return [
        {
            "judge_id": j.id,
            "judge_name": j.name,
            "adjournment_rate": judge_adjournment_rate(db, j.id),
        }
        for j in judges
    ]
