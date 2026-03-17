from __future__ import annotations

from app.db.session import SessionLocal
from app.ingestion.hearing_outcomes import reprocess_stale_hearings


def main() -> None:
    db = SessionLocal()
    try:
        count = reprocess_stale_hearings(db, limit=10000)
        print({"reprocessed": count})
    finally:
        db.close()


if __name__ == "__main__":
    main()