from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.explanations.generator import generate_and_store_case_summary
from app.impact.narratives import generate_and_store_case_impact
from app.models import Case
from app.services.importance import CaseImportanceScorer


@celery_app.task(name="app.tasks.importance_recompute.recompute_case_importance")
def recompute_case_importance(batch_size: int = 1000) -> dict:
    db = SessionLocal()
    scored = 0
    failed = 0
    try:
        scorer = CaseImportanceScorer(db)
        rows = (
            db.query(Case)
            .filter(Case.is_deleted.is_(False))
            .filter(or_(Case.last_scored_at.is_(None), Case.last_source_updated_at > Case.last_scored_at))
            .order_by(Case.id.asc())
            .limit(batch_size)
            .all()
        )

        for case in rows:
            try:
                scorer.score_and_persist_case(case, fast_pass=False)
                generate_and_store_case_summary(db, case)
                generate_and_store_case_impact(db, case)
                scored += 1
            except Exception:
                failed += 1

        db.commit()
        return {
            "scored": scored,
            "failed": failed,
            "batch_size": batch_size,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
