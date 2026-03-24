from __future__ import annotations

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.hearing_outcomes import apply_outcome_to_hearing
from app.models import Hearing


BATCH_SIZE = 500


def run_backfill(limit: int | None = None) -> dict[str, int | str]:
    settings = get_settings()
    parser_version = settings.outcome_parser_version

    db = SessionLocal()
    try:
        query = (
            db.query(Hearing)
            .filter(Hearing.is_deleted.is_(False))
            .filter(
                (Hearing.outcome_type.is_(None))
                | (Hearing.outcome_confidence.is_(None))
                | (Hearing.parser_version.is_(None))
            )
            .order_by(Hearing.date.desc(), Hearing.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)

        hearings = query.all()
        processed = 0
        for hearing in hearings:
            apply_outcome_to_hearing(
                db,
                hearing,
                raw_outcome_text=hearing.raw_outcome_text or hearing.outcome_text,
                listing_type=hearing.listing_type,
                source_name=hearing.source,
                parser_version=parser_version,
            )
            processed += 1
            if processed % BATCH_SIZE == 0:
                db.commit()
        db.commit()
        return {
            "processed": processed,
            "parser_version": parser_version,
        }
    finally:
        db.close()


if __name__ == "__main__":
    summary = run_backfill()
    print(summary)
