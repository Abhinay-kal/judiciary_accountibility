from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.cache import invalidate_namespace
from app.db.session import get_db
from app.models import Case
from app.services.importance import CaseImportanceScorer

router = APIRouter(prefix="/admin/importance", tags=["admin-importance"])


@router.get("/config")
def get_importance_config(db: Session = Depends(get_db)) -> dict[str, Any]:
    scorer = CaseImportanceScorer(db)
    row = scorer.get_or_create_config()
    return {
        "name": row.name,
        "weights_json": row.weights_json,
        "case_type_map_json": row.case_type_map_json,
        "min_confidence": row.min_confidence,
        "media_decay_lambda": row.media_decay_lambda,
        "monetary_cap": row.monetary_cap,
        "updated_by_admin_id": row.updated_by_admin_id,
        "updated_at": row.updated_at,
    }


@router.post("/{case_id}/override")
def override_case_importance(case_id: int, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    if body.get("score") is None:
        raise HTTPException(status_code=422, detail="score is required")
    if body.get("admin_id") is None:
        raise HTTPException(status_code=422, detail="admin_id is required")

    scorer = CaseImportanceScorer(db)
    scorer.override_case_importance(
        case=case,
        score=float(body["score"]),
        reason=str(body.get("reason") or "manual override"),
        admin_id=int(body["admin_id"]),
    )
    result = scorer.score_and_persist_case(case, fast_pass=False)

    db.commit()
    invalidate_namespace("cases")
    invalidate_namespace("case")

    return {
        "case_id": case.id,
        "importance_score": result.score,
        "importance_confidence": result.confidence,
        "importance_components": result.components,
        "explanation": result.explanation,
    }


@router.put("/config")
def update_importance_config(body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.get("admin_id") is None:
        raise HTTPException(status_code=422, detail="admin_id is required")

    scorer = CaseImportanceScorer(db)
    row = scorer.update_config(
        weights_json=body.get("weights_json") or CaseImportanceScorer.DEFAULT_WEIGHTS,
        case_type_map_json=body.get("case_type_map_json") or CaseImportanceScorer.DEFAULT_CASE_TYPE_MAP,
        min_confidence=float(body.get("min_confidence") if body.get("min_confidence") is not None else 0.2),
        media_decay_lambda=float(
            body.get("media_decay_lambda") if body.get("media_decay_lambda") is not None else 0.05
        ),
        monetary_cap=float(body.get("monetary_cap") if body.get("monetary_cap") is not None else 50000000.0),
        admin_id=int(body["admin_id"]),
    )
    db.commit()
    return {
        "name": row.name,
        "weights_json": row.weights_json,
        "case_type_map_json": row.case_type_map_json,
        "min_confidence": row.min_confidence,
        "media_decay_lambda": row.media_decay_lambda,
        "monetary_cap": row.monetary_cap,
        "updated_by_admin_id": row.updated_by_admin_id,
        "updated_at": row.updated_at,
    }
