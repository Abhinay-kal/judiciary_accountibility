from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json
from app.db.session import get_db
from app.models import Judge, JudgeAssignment, JudgeAttributionAudit, JudgeRegistry
from app.schemas.common import JudgeOut
from app.schemas.stats import JudgeStatsOut
from app.services.metrics import judge_adjournment_rate, judge_median_disposal_days

router = APIRouter(prefix="/judges")


@router.get("", response_model=list[JudgeOut])
def list_judges(db: Session = Depends(get_db)):
    def _produce() -> list[dict]:
        judges = db.query(Judge).filter(Judge.is_deleted.is_(False)).order_by(Judge.name.asc()).all()
        return [JudgeOut.model_validate(item).model_dump() for item in judges]

    return get_or_set_json("judges", "all", _produce)


@router.get("/{judge_id}", response_model=JudgeOut)
def get_judge(judge_id: int, db: Session = Depends(get_db)):
    def _produce() -> dict:
        judge = db.query(Judge).filter(Judge.id == judge_id, Judge.is_deleted.is_(False)).one_or_none()
        if not judge:
            raise HTTPException(status_code=404, detail="Judge not found")
        return JudgeOut.model_validate(judge).model_dump()

    return get_or_set_json("judge", str(judge_id), _produce)


@router.get("/{judge_registry_id}/profile")
def get_judge_profile(
    judge_registry_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    def _produce() -> dict:
        entry = db.get(JudgeRegistry, judge_registry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Judge registry profile not found")

        base_query = db.query(JudgeAssignment).filter(JudgeAssignment.judge_id == judge_registry_id)
        total = base_query.count()
        items = (
            base_query
            .order_by(JudgeAssignment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        merge_history = (
            db.query(JudgeAttributionAudit)
            .filter(
                JudgeAttributionAudit.judge_registry_id == judge_registry_id,
                JudgeAttributionAudit.action.in_(["merge_registry", "manual_assign"]),
            )
            .order_by(JudgeAttributionAudit.created_at.desc())
            .limit(200)
            .all()
        )

        return {
            "judge_id": entry.judge_id,
            "canonical_name": entry.canonical_name,
            "name_variants": entry.name_variants,
            "service_number": entry.service_number,
            "court_id": entry.court_id,
            "known_designations": entry.known_designations,
            "first_seen": entry.first_seen,
            "last_seen": entry.last_seen,
            "is_provisional": entry.is_provisional,
            "metadata": entry.metadata_json,
            "linked_hearings": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "assignment_id": item.assignment_id,
                        "hearing_id": item.hearing_id,
                        "judge_name_raw": item.judge_name_raw,
                        "role": item.role.value,
                        "sequence_index": item.sequence_index,
                        "attribution_confidence": item.attribution_confidence,
                        "matched_on": item.matched_on,
                        "source_id": item.source_id,
                        "ingestion_run_id": item.ingestion_run_id,
                    }
                    for item in items
                ],
            },
            "merge_history": [
                {
                    "audit_id": audit.id,
                    "action": audit.action,
                    "admin_id": audit.admin_id,
                    "reason": audit.reason,
                    "old_value": audit.old_value,
                    "new_value": audit.new_value,
                    "created_at": audit.created_at,
                }
                for audit in merge_history
            ],
            "csv_export_hint": "/api/v1/judges/%s/profile?format=csv" % entry.judge_id,
        }

    return get_or_set_json("judge_profile", f"{judge_registry_id}|{page}|{page_size}", _produce)


@router.get("/{judge_id}/stats", response_model=JudgeStatsOut)
def get_judge_stats(judge_id: int, db: Session = Depends(get_db)):
    def _produce() -> dict:
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
        ).model_dump()

    return get_or_set_json("judge_stats", str(judge_id), _produce)
