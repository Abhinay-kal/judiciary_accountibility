from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json
from app.db.session import get_db
from app.moderation.renderer import render_public_text
from app.models import Flag
from app.schemas.common import FlagOut

router = APIRouter(prefix="/flags")


@router.get("", response_model=dict)
def list_flags(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = f"page={page}|page_size={page_size}"

    def _produce() -> dict:
        query = db.query(Flag).filter(Flag.is_deleted.is_(False), Flag.is_active.is_(True))
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        serialized = []
        for item in items:
            payload = FlagOut.model_validate(item).model_dump()
            details = payload.get("details") or {}
            summary_text = str(details.get("summary") or details.get("reason") or "")
            if summary_text:
                rendered, meta = render_public_text(
                    summary_text,
                    labels=[details.get("defamation_label") or "UNVERIFIED"],
                    parser_confidence=details.get("parser_confidence"),
                    source_links=details.get("source_links") or [],
                )
                payload["details"]["summary"] = rendered
                payload["details"]["moderation_render_meta"] = meta
            serialized.append(payload)
        return {
            "items": serialized,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return get_or_set_json("flags", cache_key, _produce)
