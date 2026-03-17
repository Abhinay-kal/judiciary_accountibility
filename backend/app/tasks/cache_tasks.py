from __future__ import annotations

import logging

from app.cache.warmup import refresh_precomputed_tables, warmup_top_case_ids
from app.celery_app import celery_app
from app.core.cache import get_or_set_json
from app.db.session import SessionLocal
from app.models import Case, Hearing

logger = logging.getLogger(__name__)


def _warm_case_payload(db, case_id: int) -> dict:
    from app.api.routes.cases import _serialize_case

    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if not case:
        return {}
    return _serialize_case(case, db)


def _warm_case_timeline_payload(db, case_id: int) -> list[dict]:
    hearings = (
        db.query(Hearing)
        .filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False))
        .order_by(Hearing.date.asc())
        .all()
    )
    payload: list[dict] = []
    for item in hearings:
        payload.append(
            {
                "id": item.id,
                "case_id": item.case_id,
                "date": item.date,
                "purpose": item.purpose,
                "outcome_text": item.outcome_text,
                "source_url": item.source_url,
                "source_ref": item.source_ref,
                "judge_id": item.judge_id,
                "outcome_type": item.outcome_type.value if item.outcome_type else None,
                "outcome_confidence": item.outcome_confidence,
            }
        )
    return payload


@celery_app.task(name="app.tasks.cache_tasks.refresh_precomputed_cache")
def refresh_precomputed_cache() -> dict:
    db = SessionLocal()
    try:
        return refresh_precomputed_tables(db)
    finally:
        db.close()


@celery_app.task(name="app.tasks.cache_tasks.warmup_hot_case_cache")
def warmup_hot_case_cache(limit: int = 100) -> dict:
    db = SessionLocal()
    warmed_case = 0
    warmed_timeline = 0
    try:
        case_ids = warmup_top_case_ids(db, limit=max(1, limit))
        for case_id in case_ids:
            payload = get_or_set_json(
                "case",
                str(case_id),
                lambda current_id=case_id: _warm_case_payload(db, current_id),
            )
            if payload:
                warmed_case += 1

            timeline = get_or_set_json(
                "case_timeline",
                str(case_id),
                lambda current_id=case_id: _warm_case_timeline_payload(db, current_id),
            )
            if timeline is not None:
                warmed_timeline += 1

        return {
            "requested": limit,
            "candidate_case_ids": len(case_ids),
            "warmed_case": warmed_case,
            "warmed_timeline": warmed_timeline,
        }
    finally:
        db.close()


def run_startup_cache_warmup() -> None:
    db = SessionLocal()
    try:
        refresh_precomputed_tables(db)
        hot_case_ids = warmup_top_case_ids(db, limit=25)
        for case_id in hot_case_ids:
            try:
                get_or_set_json(
                    "case",
                    str(case_id),
                    lambda current_id=case_id: _warm_case_payload(db, current_id),
                )
            except Exception:
                logger.exception("Startup warmup failed for case=%s", case_id)
    except Exception:
        logger.exception("Startup cache warmup failed")
    finally:
        db.close()
