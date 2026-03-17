from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache import invalidate_namespace
from app.db.session import get_db
from app.models import JudgeAssignment, JudgeAttributionAudit, JudgeRegistry
from app.services.judge_resolution import suggest_registry_merges

router = APIRouter(prefix="/admin/judges", tags=["admin-judges"])


@router.get("/review")
def review_judge_attribution(
    confidence_threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    low_confidence = (
        db.query(JudgeAssignment)
        .filter(JudgeAssignment.attribution_confidence < confidence_threshold)
        .order_by(JudgeAssignment.created_at.desc())
        .limit(limit)
        .all()
    )
    provisional = (
        db.query(JudgeRegistry)
        .filter(JudgeRegistry.is_provisional.is_(True))
        .order_by(JudgeRegistry.updated_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "confidence_threshold": confidence_threshold,
        "low_confidence_assignments": [
            {
                "assignment_id": item.assignment_id,
                "hearing_id": item.hearing_id,
                "judge_id": item.judge_id,
                "judge_name_raw": item.judge_name_raw,
                "attribution_confidence": item.attribution_confidence,
                "matched_on": item.matched_on,
            }
            for item in low_confidence
        ],
        "provisional_registry": [
            {
                "judge_id": item.judge_id,
                "canonical_name": item.canonical_name,
                "court_id": item.court_id,
                "name_variants": item.name_variants,
                "last_seen": item.last_seen,
            }
            for item in provisional
        ],
        "merge_suggestions": suggest_registry_merges(db, limit=limit),
    }


@router.post("/{registry_id}/merge")
def merge_registry_entries(
    registry_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    target = db.get(JudgeRegistry, registry_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target registry entry not found")

    candidate_ids: list[str] = body.get("candidate_ids") or []
    admin_id = body.get("admin_id")
    reason = body.get("reason") or "manual merge"
    merged = []

    for candidate_id in candidate_ids:
        if candidate_id == registry_id:
            continue
        candidate = db.get(JudgeRegistry, candidate_id)
        if candidate is None:
            continue

        assignments = db.query(JudgeAssignment).filter(JudgeAssignment.judge_id == candidate.judge_id).all()
        for assignment in assignments:
            conflict = (
                db.query(JudgeAssignment)
                .filter(
                    JudgeAssignment.hearing_id == assignment.hearing_id,
                    JudgeAssignment.judge_id == target.judge_id,
                    JudgeAssignment.sequence_index == assignment.sequence_index,
                    JudgeAssignment.assignment_id != assignment.assignment_id,
                )
                .first()
            )
            if conflict is not None:
                assignment.sequence_index = assignment.sequence_index + 100
            assignment.judge_id = target.judge_id

        target_variants = set(target.name_variants.get("variants", []))
        target_variants.update(candidate.name_variants.get("variants", []))
        target.name_variants = {"variants": sorted(target_variants)}
        target.is_provisional = False

        db.add(
            JudgeAttributionAudit(
                action="merge_registry",
                judge_registry_id=target.judge_id,
                admin_id=admin_id,
                reason=reason,
                old_value={"target": target.judge_id, "candidate": candidate.judge_id},
                new_value={"target": target.judge_id, "merged_into": target.judge_id},
            )
        )

        candidate.is_provisional = True
        candidate.metadata_json = {
            **candidate.metadata_json,
            "merged_into": target.judge_id,
            "merged_at": datetime.utcnow().isoformat(),
        }
        merged.append(candidate.judge_id)

    db.commit()
    invalidate_namespace("judges")
    return {"target": registry_id, "merged": merged}
