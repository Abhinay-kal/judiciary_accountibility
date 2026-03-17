from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json
from app.db.session import get_db
from app.models import Court
from app.schemas.common import CourtOut

router = APIRouter(prefix="/courts")


@router.get("", response_model=list[CourtOut])
def list_courts(db: Session = Depends(get_db)):
    def _produce() -> list[dict]:
        items = db.query(Court).filter(Court.is_deleted.is_(False)).order_by(Court.name.asc()).all()
        return [CourtOut.model_validate(item).model_dump() for item in items]

    return get_or_set_json("courts", "all", _produce)
