from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes import corrections
from app.db.session import get_db

router = APIRouter(prefix="/admin/corrections", tags=["admin-corrections"])


@router.get("/pending")
def pending(
    status: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    requester: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return corrections.admin_pending_corrections(
        status=status,
        target_type=target_type,
        target_id=target_id,
        requester=requester,
        db=db,
    )


@router.post("/{request_id}/assign")
def assign(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    return corrections.assign_correction_request(request_id=request_id, body=body, db=db)


@router.post("/{request_id}/review")
def review(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    return corrections.review_correction_request_endpoint(request_id=request_id, body=body, db=db)


@router.post("/{request_id}/publish-response")
def publish_response(request_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    return corrections.publish_correction_response(request_id=request_id, body=body, db=db)
