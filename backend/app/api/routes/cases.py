from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Case, Hearing
from app.schemas.common import CaseOut, HearingOut
from app.schemas.query import CaseQuery
from app.services.query import apply_case_filters, paginate

router = APIRouter(prefix="/cases")


@router.get("", response_model=dict)
def list_cases(
    court: Optional[str] = None,
    state: Optional[str] = None,
    case_type: Optional[str] = None,
    party_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    flagged_only: bool = False,
    politician_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    filters = CaseQuery(
        court=court,
        state=state,
        case_type=case_type,
        party_name=party_name,
        start_date=start_date,
        end_date=end_date,
        flagged_only=flagged_only,
        politician_only=politician_only,
        page=page,
        page_size=page_size,
    )

    query = db.query(Case).filter(Case.is_deleted.is_(False))
    query = apply_case_filters(query, filters)
    items, total = paginate(query, page, page_size)

    return {
        "items": [CaseOut.model_validate(item).model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}/timeline", response_model=list[HearingOut])
def get_case_timeline(case_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Hearing)
        .filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False))
        .order_by(Hearing.date.asc())
        .all()
    )
