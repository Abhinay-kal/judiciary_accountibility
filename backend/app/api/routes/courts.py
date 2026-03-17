from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Court
from app.schemas.common import CourtOut

router = APIRouter(prefix="/courts")


@router.get("", response_model=list[CourtOut])
def list_courts(db: Session = Depends(get_db)):
    return db.query(Court).filter(Court.is_deleted.is_(False)).order_by(Court.name.asc()).all()
