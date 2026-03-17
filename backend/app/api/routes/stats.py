from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json_meta
from app.db.session import get_db
from app.models import Court, CourtStatsCache, Judge, JudgeStatsCache
from app.schemas.stats import CourtStatsOut
from app.services.metrics import backlog_indicators, judge_adjournment_rate

router = APIRouter(prefix="/stats")


@router.get("/court", response_model=list[CourtStatsOut])
def get_court_stats(db: Session = Depends(get_db)):
    def _produce() -> list[dict]:
        precomputed = db.query(CourtStatsCache).order_by(CourtStatsCache.backlog_ratio.desc()).all()
        if precomputed:
            output = []
            for row in precomputed:
                court = db.query(Court).filter(Court.id == row.court_id, Court.is_deleted.is_(False)).first()
                if not court:
                    continue
                output.append(
                    CourtStatsOut(
                        court_id=court.id,
                        court_name=court.name,
                        total_cases=row.total_cases,
                        pending_cases=row.pending_cases,
                        disposed_cases=row.disposed_cases,
                        backlog_ratio=row.backlog_ratio,
                    ).model_dump()
                )
            if output:
                return output

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
                ).model_dump()
            )
        return output

    payload, _ = get_or_set_json_meta("stats_court", "all", _produce)
    return payload


@router.get("/judge")
def get_judge_stats_summary(db: Session = Depends(get_db)):
    def _produce() -> list[dict]:
        precomputed = db.query(JudgeStatsCache).order_by(JudgeStatsCache.hearing_count.desc()).all()
        if precomputed:
            out = []
            for row in precomputed:
                judge = db.query(Judge).filter(Judge.id == row.judge_id, Judge.is_deleted.is_(False)).first()
                if not judge:
                    continue
                out.append(
                    {
                        "judge_id": judge.id,
                        "judge_name": judge.name,
                        "adjournment_rate": round(1.0 - min(1.0, row.avg_outcome_confidence), 3),
                        "source": "precomputed",
                    }
                )
            if out:
                return out

        judges = db.query(Judge).filter(Judge.is_deleted.is_(False)).all()
        return [
            {
                "judge_id": j.id,
                "judge_name": j.name,
                "adjournment_rate": judge_adjournment_rate(db, j.id),
                "source": "live",
            }
            for j in judges
        ]

    payload, meta = get_or_set_json_meta("stats_judge", "all", _produce)
    return {"items": payload, "cache_meta": meta}
