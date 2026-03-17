from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.orm import Session

from app.ingestion.models import RawPayload

logger = logging.getLogger(__name__)


class DeferredBatchJobs:
    """Heavy NLP/ML jobs intentionally decoupled from ingestion hot path."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_text_index(self, batch_size: int = 500) -> dict:
        """Placeholder text-index batch.

        Keep ingestion minimal: this should run on schedule, not inline.
        """
        counts = Counter()
        rows = self.db.query(RawPayload).order_by(RawPayload.payload_id.desc()).limit(batch_size).all()
        for row in rows:
            media = (row.media_type or "unknown").lower()
            counts[media] += 1
        logger.info("Deferred text indexing scanned %d payloads", len(rows))
        return {"scanned": len(rows), "by_media_type": dict(counts)}

    def run_nlp_enrichment(self, batch_size: int = 300) -> dict:
        rows = self.db.query(RawPayload.payload_id).order_by(RawPayload.payload_id.desc()).limit(batch_size).all()
        logger.info("Deferred NLP enrichment queued %d payload references", len(rows))
        return {"queued": len(rows)}
