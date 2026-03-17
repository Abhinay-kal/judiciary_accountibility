from __future__ import annotations

from app.celery_app import celery_app
from app.db.session import SessionLocal


@celery_app.task(name="app.tasks.hearing_outcomes.retrain_hearing_outcome_model")
def retrain_hearing_outcome_model() -> dict:
    from app.ml.hearing_outcomes import OutcomeMLParser

    db = SessionLocal()
    try:
        return OutcomeMLParser().train_from_annotations(db)
    finally:
        db.close()


@celery_app.task(name="app.tasks.hearing_outcomes.reprocess_hearing_outcomes")
def reprocess_hearing_outcomes(parser_version: str | None = None, limit: int = 200) -> dict:
    from app.ingestion.hearing_outcomes import reprocess_stale_hearings

    db = SessionLocal()
    try:
        count = reprocess_stale_hearings(db, parser_version=parser_version, limit=limit)
        return {"reprocessed": count, "parser_version": parser_version}
    finally:
        db.close()