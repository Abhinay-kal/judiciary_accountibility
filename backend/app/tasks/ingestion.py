from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.celery_app import celery_app
from app.core.cache import invalidate_for_event
from app.core.monitoring import INGESTION_RECORDS_TOTAL
from app.db.session import SessionLocal
from app.scrapers.sources.ecourts import ECourtsScraper
from app.scrapers.sources.high_court import HighCourtCauseListScraper
from app.scrapers.sources.njdg import NJDGScraper
from app.scrapers.sources.supreme_court import SupremeCourtCauseListScraper
from app.services.metrics import run_anomaly_detection
from app.services.normalization import (
    create_ingestion_log,
    normalize_case_record,
    upsert_case_from_normalized,
    upsert_hearings_for_case,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ingestion.run_daily_ingestion")
def run_daily_ingestion() -> dict:
    """Daily ingestion task that fetches all configured sources."""

    run_id = datetime.utcnow().strftime("%Y%m%d") + "-" + str(uuid.uuid4())[:8]
    db = SessionLocal()
    scrapers = [NJDGScraper(), ECourtsScraper(), HighCourtCauseListScraper(), SupremeCourtCauseListScraper()]

    processed = 0
    failed = 0

    try:
        for scraper in scrapers:
            try:
                items = scraper.run()
                for raw, record in items:
                    normalized = normalize_case_record(record)
                    case = upsert_case_from_normalized(db, normalized)
                    upsert_hearings_for_case(
                        db,
                        case,
                        record,
                        scraper.source_name,
                        ingestion_run_id=run_id,
                    )
                    create_ingestion_log(
                        db,
                        source=scraper.source_name,
                        run_id=run_id,
                        source_url=raw.url,
                        status="success",
                        raw_storage_path=raw.raw_storage_path,
                        checksum=raw.checksum,
                        metadata_json={"content_type": raw.content_type},
                    )
                    processed += 1
                    INGESTION_RECORDS_TOTAL.labels(source=scraper.source_name, result="success").inc()
                db.commit()
            except Exception as exc:
                db.rollback()
                failed += 1
                INGESTION_RECORDS_TOTAL.labels(source=scraper.source_name, result="failed").inc()
                create_ingestion_log(
                    db,
                    source=scraper.source_name,
                    run_id=run_id,
                    source_url=None,
                    status="failed",
                    raw_storage_path=None,
                    checksum=None,
                    error_message=str(exc),
                )
                db.commit()
                logger.exception("Ingestion failed for %s", scraper.source_name)

        flagged = run_anomaly_detection(db)
        invalidate_for_event("INGESTION_COMPLETED")

        return {"run_id": run_id, "processed": processed, "failed": failed, "flagged": flagged}
    finally:
        db.close()
