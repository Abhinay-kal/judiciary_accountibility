from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Flag
from app.schemas.common import FlagOut

router = APIRouter(prefix="/flags")


@router.get("", response_model=dict)
def list_flags(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Flag).filter(Flag.is_deleted.is_(False), Flag.is_active.is_(True))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [FlagOut.model_validate(item).model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
