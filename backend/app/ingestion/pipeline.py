"""Core ten-step resilient ingestion pipeline.

Each invocation of :meth:`ResilientIngestionPipeline.run` executes the
following steps in order, catching exceptions at each boundary so that
failures are isolated and recorded — never silent:

1.  **Start run** — persist a new :class:`~app.ingestion.models.IngestionRun`
    row with status ``RUNNING``.
2.  **Fetch with retries** — HTTP GET with exponential backoff; falls
    back to mirror URLs automatically.
3.  **HTTP validation** — 4 xx / 5 xx responses abort with ``RUN_FAILED``.
4.  **Schema change detection** — compares payload against the stored
    baseline; writes the new snapshot back to *source*.
5.  **Parse** — delegates to the source's registered
    :class:`~app.scrapers.base.BaseScraper` subclass.
6.  **Volume anomaly detection** — compares record count against rolling
    history.
7.  **Raw-payload storage** — persists raw bytes to disk (size-limited).
8.  **Upsert normalised records** — calls
    :func:`~app.services.normalization.upsert_case_from_normalized`.
9.  **Prometheus metrics** — updated atomically after upsert.
10. **Source health update** — transitions the source health FSM.

Usage::

    pipeline = ResilientIngestionPipeline(db, settings)
    run = pipeline.run(source)
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.ingestion.config import IngestionSettings
from app.ingestion.detectors.parser_confidence import ParserConfidenceScorer
from app.ingestion.detectors.schema_change import SchemaChangeDetector
from app.ingestion.detectors.volume_anomaly import VolumeAnomalyDetector
from app.ingestion.health import update_source_health
from app.ingestion.metrics import (
    DUPLICATE_RATE,
    INGEST_CONFIDENCE_SCORE,
    INGEST_HTTP_ERRORS,
    INGEST_LATENCY_SECONDS,
    INGEST_RECORDS_PROCESSED,
    INGEST_RUN_TOTAL,
    INGEST_SCHEMA_CHANGES,
    INGEST_VOLUME_ANOMALIES,
    RAW_BYTES_INGESTED,
    record_health_gauge,
)
from app.ingestion.models import (
    HEALTH_DISABLED,
    RUN_FAILED,
    RUN_PARTIAL,
    RUN_SUCCESS,
    SOURCE_HTML,
    SOURCE_JSON,
    IngestionRun,
    IngestionSource,
)
from app.ingestion.cas import store_payload
from app.scrapers.sources import (
    ECourtsScraper,
    HighCourtCauseListScraper,
    NJDGScraper,
    SupremeCourtCauseListScraper,
)
from app.storage.storage_client import StorageClient

logger = logging.getLogger(__name__)

_RUNNING = "RUNNING"


class ResilientIngestionPipeline:
    """Orchestrates all ten steps for a single source ingestion run."""

    def __init__(self, db: Session, settings: IngestionSettings) -> None:
        self._db = db
        self._s = settings
        self._http = requests.Session()
        self._http.headers.update({"User-Agent": "JudiciaryTracker/1.0"})
        self._storage = StorageClient(base_dir=self._s.ingest_raw_storage_dir)

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    def run(self, source: IngestionSource) -> IngestionRun:
        """Execute all ten steps for *source*.

        Returns the completed (persisted) :class:`IngestionRun` regardless
        of whether the run succeeded or failed.
        """
        if source.health_status == HEALTH_DISABLED or not source.is_active:
            logger.info("Source '%s' is disabled — skipping.", source.source_name)
            # Create a short-circuit run record
            run = self._make_run(source)
            run.status = RUN_FAILED
            run.error_summary = "Source is disabled"
            self._finalise(source, run)
            return run

        run = self._make_run(source)           # step 1
        t0 = time.monotonic()

        # ------------------------------------------------------------------
        # Step 2 — Fetch with retries
        # ------------------------------------------------------------------
        content, http_status = self._fetch_with_retries(source, run)
        run.http_status = http_status

        # ------------------------------------------------------------------
        # Step 3 — HTTP validation
        # ------------------------------------------------------------------
        if content is None or http_status >= 400:
            run.status = RUN_FAILED
            run.error_summary = run.error_summary or f"HTTP {http_status}"
            INGEST_HTTP_ERRORS.labels(
                source_name=source.source_name,
                status_code=str(http_status or 0),
            ).inc()
            self._record_latency(source.source_name, t0)
            self._finalise(source, run)
            return run

        # ------------------------------------------------------------------
        # Step 4 — Schema change detection
        # ------------------------------------------------------------------
        schema_changed, new_snapshot = self._check_schema(source, content)
        run.schema_change_detected = schema_changed
        if schema_changed:
            INGEST_SCHEMA_CHANGES.labels(source_name=source.source_name).inc()
            logger.warning(
                "Schema change detected for source '%s'.", source.source_name
            )

        # ------------------------------------------------------------------
        # Step 5 — Parse
        # ------------------------------------------------------------------
        records, parse_errors = self._parse(source, content, run)

        # ------------------------------------------------------------------
        # Step 6 — Volume anomaly detection
        # ------------------------------------------------------------------
        self._check_volume_anomaly(source, run, len(records))

        # ------------------------------------------------------------------
        # Step 7 — Store raw payload
        # ------------------------------------------------------------------
        raw_path = self._store_raw(source, run, content)
        run.raw_payload_location = raw_path

        # ------------------------------------------------------------------
        # Step 8 — Upsert normalised records
        # ------------------------------------------------------------------
        inserted, failed = self._upsert_records(source, records, run)

        # ------------------------------------------------------------------
        # Step 9 — Prometheus metrics
        # ------------------------------------------------------------------
        conf_score = self._compute_confidence(source, records, parse_errors)
        run.parser_confidence_score = conf_score
        run.records_fetched = len(records) + parse_errors
        run.records_parsed = len(records)
        run.records_inserted = inserted
        run.records_failed = failed + parse_errors

        INGEST_RECORDS_PROCESSED.labels(
            source_name=source.source_name, outcome="inserted"
        ).inc(inserted)
        INGEST_RECORDS_PROCESSED.labels(
            source_name=source.source_name, outcome="failed"
        ).inc(failed + parse_errors)
        INGEST_CONFIDENCE_SCORE.labels(source_name=source.source_name).set(conf_score)

        # Determine final run status
        if failed + parse_errors == 0 and not schema_changed:
            run.status = RUN_SUCCESS
        elif inserted > 0:
            run.status = RUN_PARTIAL
        else:
            run.status = RUN_FAILED

        self._record_latency(source.source_name, t0)
        INGEST_RUN_TOTAL.labels(
            source_name=source.source_name, status=run.status
        ).inc()

        # ------------------------------------------------------------------
        # Step 10 — Update source health FSM
        # ------------------------------------------------------------------
        new_health = update_source_health(source, run, self._s)
        record_health_gauge(source.source_name, new_health)

        if new_snapshot is not None:
            source.schema_baseline = new_snapshot

        self._finalise(source, run)
        return run

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _make_run(self, source: IngestionSource) -> IngestionRun:
        run = IngestionRun(
            run_id=str(uuid.uuid4()),
            source_id=source.id,
            started_at=datetime.now(timezone.utc),
            status=_RUNNING,
            parser_version=source.parser_version,
            provenance_json={
                "source_name": source.source_name,
                "source_type": source.source_type,
            },
        )
        self._db.add(run)
        self._db.flush()  # assign DB id without committing outer txn
        return run

    def _fetch_with_retries(
        self,
        source: IngestionSource,
        run: IngestionRun,
    ) -> tuple[Optional[bytes], int]:
        """Try base_url then mirror URLs with exponential back-off."""
        urls = [source.base_url] + list(source.mirror_urls or [])
        last_status = 0
        for attempt in range(self._s.ingest_retry_limit + 1):
            delay = self._s.ingest_backoff_base_seconds * (2 ** attempt)
            if attempt > 0:
                logger.info(
                    "Source '%s' retry %d/%d after %ds back-off.",
                    source.source_name,
                    attempt,
                    self._s.ingest_retry_limit,
                    delay,
                )
                time.sleep(delay)

            # Rotate through available URLs on retries
            url = urls[min(attempt, len(urls) - 1)]
            try:
                resp = self._http.get(url, timeout=30)
                last_status = resp.status_code
                if resp.status_code < 400:
                    return resp.content, resp.status_code
                run.error_summary = f"HTTP {resp.status_code} from {url}"
            except requests.RequestException as exc:
                last_status = 0
                run.error_summary = f"Fetch error: {exc}"
                logger.warning("Source '%s' fetch error: %s", source.source_name, exc)

        return None, last_status

    def _check_schema(
        self,
        source: IngestionSource,
        content: bytes,
    ) -> tuple[bool, Optional[dict]]:
        detector = SchemaChangeDetector(
            threshold=self._s.ingest_schema_mismatch_threshold,
            source_config=source.config_json or {},
        )
        baseline = source.schema_baseline

        if source.source_type == SOURCE_HTML:
            result = detector.check_html(content, baseline)
        elif source.source_type == SOURCE_JSON:
            try:
                import json as _json
                payload = _json.loads(content)
            except Exception:
                payload = {}
            result = detector.check_json(payload, baseline)
        else:
            return False, None

        return result.is_changed, result.new_snapshot

    def _parse(
        self,
        source: IngestionSource,
        content: bytes,
        run: IngestionRun,
    ) -> tuple[list[dict], int]:
        """Delegate to the source's registered scraper."""
        from app.scrapers.base import ScrapeResult

        scraper_cls = self._resolve_scraper(source)
        if scraper_cls is None:
            logger.warning(
                "No scraper registered for source '%s' — skipping parse.",
                source.source_name,
            )
            return [], 0

        scraper = scraper_cls()
        raw = ScrapeResult(
            source=source.source_name,
            url=source.base_url,
            content=content,
            content_type="text/html",
            checksum="",
            raw_storage_path="",
        )
        records: list[dict] = []
        parse_errors = 0
        try:
            parsed = scraper.parse(raw)
            records = parsed if parsed else []
        except Exception as exc:
            parse_errors = 1
            run.error_summary = (run.error_summary or "") + f" | parse error: {exc}"
            logger.exception(
                "Parse error for source '%s': %s", source.source_name, exc
            )

        return records, parse_errors

    def _check_volume_anomaly(
        self,
        source: IngestionSource,
        run: IngestionRun,
        current_count: int,
    ) -> None:
        from sqlalchemy import desc

        history = (
            self._db.query(IngestionRun.records_fetched)
            .filter(
                IngestionRun.source_id == source.id,
                IngestionRun.status.in_([RUN_SUCCESS, RUN_PARTIAL]),
                IngestionRun.records_fetched.isnot(None),
            )
            .order_by(desc(IngestionRun.started_at))
            .limit(10)
            .all()
        )
        historical = [row[0] for row in history]
        detector = VolumeAnomalyDetector(threshold=self._s.ingest_volume_anomaly_ratio)
        result = detector.check(current_count, historical)
        run.volume_anomaly_detected = result.is_anomaly
        if result.is_anomaly:
            INGEST_VOLUME_ANOMALIES.labels(
                source_name=source.source_name, direction=result.direction
            ).inc()
            logger.warning(
                "Volume anomaly '%s' for '%s': current=%d, median=%.1f",
                result.direction,
                source.source_name,
                current_count,
                result.rolling_median,
            )

    def _store_raw(
        self,
        source: IngestionSource,
        run: IngestionRun,
        content: bytes,
    ) -> Optional[str]:
        max_bytes = self._s.ingest_max_raw_payload_mb * 1024 * 1024
        if len(content) > max_bytes:
            logger.warning(
                "Raw payload for '%s' exceeds size limit (%dMB) — not stored.",
                source.source_name,
                self._s.ingest_max_raw_payload_mb,
            )
            return None
        try:
            RAW_BYTES_INGESTED.labels(source_name=source.source_name).inc(len(content))
            cas_result = store_payload(
                self._db,
                self._storage,
                payload=content,
                media_type=source.source_type,
                source_id=source.id,
                ingestion_run_id=run.id,
                provenance={"run_id": run.run_id, "source": source.source_name},
            )
            run.raw_payload_checksum = cas_result.checksum
            run.raw_object_ref = cas_result.storage_ref
            duplicate_rate = 1.0 if cas_result.is_duplicate else 0.0
            DUPLICATE_RATE.labels(source_name=source.source_name).set(duplicate_rate)
            return cas_result.storage_ref
        except Exception as exc:
            logger.error(
                "Failed to store raw payload for '%s': %s", source.source_name, exc
            )
            return None

    def _upsert_records(
        self,
        source: IngestionSource,
        records: list[dict],
        run: IngestionRun,
    ) -> tuple[int, int]:
        from app.services.normalization import normalize_case_record, upsert_case_from_normalized

        inserted = 0
        failed = 0
        for raw_rec in records:
            try:
                normalized = normalize_case_record(raw_rec)
                upsert_case_from_normalized(self._db, normalized)
                inserted += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "Upsert failed for source '%s', record %r: %s",
                    source.source_name,
                    raw_rec.get("case_id"),
                    exc,
                )

        if records:
            try:
                self._db.flush()
            except Exception as exc:
                logger.error("DB flush error for '%s': %s", source.source_name, exc)

        return inserted, failed

    @staticmethod
    def _compute_confidence(
        source: IngestionSource,
        records: list[dict],
        parse_errors: int,
    ) -> float:
        config = source.config_json or {}
        required_fields = config.get("required_fields", [])
        scorer = ParserConfidenceScorer(required_fields=required_fields)
        return scorer.score(records, parse_error_count=parse_errors)

    def _finalise(self, source: IngestionSource, run: IngestionRun) -> None:
        run.finished_at = datetime.now(timezone.utc)
        source.last_attempt_at = run.finished_at
        try:
            self._db.commit()
        except Exception as exc:
            self._db.rollback()
            logger.error(
                "Failed to commit run for source '%s': %s",
                source.source_name,
                exc,
            )

    @staticmethod
    def _record_latency(source_name: str, t0: float) -> None:
        INGEST_LATENCY_SECONDS.labels(source_name=source_name).observe(
            time.monotonic() - t0
        )

    # ------------------------------------------------------------------
    # Scraper registry
    # ------------------------------------------------------------------

    _SCRAPER_REGISTRY: dict[str, type] = {
        # Canonical scraper source names
        "njdg": NJDGScraper,
        "ecourts": ECourtsScraper,
        "supreme_court": SupremeCourtCauseListScraper,
        "high_court": HighCourtCauseListScraper,
        # Backward-compatible aliases for existing ingestion_sources rows
        "ecourts_services": ECourtsScraper,
        "supreme_court_causelist": SupremeCourtCauseListScraper,
    }

    @classmethod
    def register_scraper(cls, source_name: str, scraper_cls: type) -> None:
        """Register a :class:`~app.scrapers.base.BaseScraper` subclass
        for a given *source_name*.  Called at module import time by each
        scraper module.
        """
        cls._SCRAPER_REGISTRY[source_name] = scraper_cls

    @classmethod
    def _resolve_scraper(cls, source: IngestionSource) -> Optional[type]:
        return cls._SCRAPER_REGISTRY.get(source.source_name)
