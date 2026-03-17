from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Judge
from app.schemas.common import JudgeOut
from app.schemas.stats import JudgeStatsOut
from app.services.metrics import judge_adjournment_rate, judge_median_disposal_days

router = APIRouter(prefix="/judges")


@router.get("", response_model=list[JudgeOut])
def list_judges(db: Session = Depends(get_db)):
    return db.query(Judge).filter(Judge.is_deleted.is_(False)).order_by(Judge.name.asc()).all()


@router.get("/{judge_id}", response_model=JudgeOut)
def get_judge(judge_id: int, db: Session = Depends(get_db)):
    judge = db.query(Judge).filter(Judge.id == judge_id, Judge.is_deleted.is_(False)).one_or_none()
    if not judge:
        raise HTTPException(status_code=404, detail="Judge not found")
    return judge


@router.get("/{judge_id}/stats", response_model=JudgeStatsOut)
def get_judge_stats(judge_id: int, db: Session = Depends(get_db)):
    judge = db.query(Judge).filter(Judge.id == judge_id, Judge.is_deleted.is_(False)).one_or_none()
    if not judge:
        raise HTTPException(status_code=404, detail="Judge not found")
    total_hearings = len([h for h in judge.hearings if not h.is_deleted])
    return JudgeStatsOut(
        judge_id=judge.id,
        judge_name=judge.name,
        total_hearings=total_hearings,
        adjournment_rate=judge_adjournment_rate(db, judge.id),
        median_disposal_days=judge_median_disposal_days(db, judge.id),
    )
