"""Prometheus metrics for the resilient ingestion subsystem.

All counters and histograms use the ``justice_ingest_`` prefix so they are
clearly grouped in Grafana dashboards.

Usage::

    from app.ingestion.metrics import (
        INGEST_RUN_TOTAL,
        INGEST_LATENCY_SECONDS,
        INGEST_RECORDS_PROCESSED,
        INGEST_SCHEMA_CHANGES,
        INGEST_VOLUME_ANOMALIES,
        INGEST_CONFIDENCE_SCORE,
        INGEST_HTTP_ERRORS,
        INGEST_SOURCE_HEALTH,
    )
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# Per-run outcome counter — labels: source_name, status (SUCCESS|PARTIAL|FAILED)
INGEST_RUN_TOTAL = Counter(
    "justice_ingest_run_total",
    "Total ingestion runs",
    ["source_name", "status"],
)

# End-to-end fetch-parse-insert latency — label: source_name
INGEST_LATENCY_SECONDS = Histogram(
    "justice_ingest_latency_seconds",
    "End-to-end ingestion latency in seconds",
    ["source_name"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, float("inf")),
)

# Records processed — labels: source_name, outcome (inserted|failed|skipped)
INGEST_RECORDS_PROCESSED = Counter(
    "justice_ingest_records_processed_total",
    "Records processed during ingestion",
    ["source_name", "outcome"],
)

# Schema change detections — label: source_name
INGEST_SCHEMA_CHANGES = Counter(
    "justice_ingest_schema_changes_total",
    "Number of detected schema changes",
    ["source_name"],
)

# Volume anomaly detections — labels: source_name, direction (spike|drop)
INGEST_VOLUME_ANOMALIES = Counter(
    "justice_ingest_volume_anomalies_total",
    "Volume outlier events (record count deviates from rolling median)",
    ["source_name", "direction"],
)

# Parser confidence gauge (last run value) — label: source_name
INGEST_CONFIDENCE_SCORE = Gauge(
    "justice_ingest_parser_confidence_score",
    "Parser confidence score from the most recent run",
    ["source_name"],
)

# HTTP error counter — labels: source_name, status_code
INGEST_HTTP_ERRORS = Counter(
    "justice_ingest_http_errors_total",
    "HTTP errors during source fetches",
    ["source_name", "status_code"],
)

# Source health encodes the enum as a numeric (0=HEALTHY, 1=DEGRADED, 2=FAILED, 3=DISABLED)
INGEST_SOURCE_HEALTH = Gauge(
    "justice_ingest_source_health",
    "Current health status of an ingestion source (0=HEALTHY,1=DEGRADED,2=FAILED,3=DISABLED)",
    ["source_name"],
)

# Alerts fired — labels: source_name, alert_type, channel
INGEST_ALERTS_TOTAL = Counter(
    "justice_ingest_alerts_total",
    "Alerts fired by the ingestion monitor",
    ["source_name", "alert_type", "channel"],
)

HEARING_OUTCOME_TOTAL = Counter(
    "justice_hearing_outcome_total",
    "Distribution of canonical hearing outcomes",
    ["source_name", "outcome_type", "parser_version"],
)

HEARING_OUTCOME_CONFIDENCE = Histogram(
    "justice_hearing_outcome_confidence",
    "Histogram of hearing outcome parser confidence",
    ["source_name", "parser_version"],
    buckets=(0.1, 0.25, 0.5, 0.6, 0.75, 0.9, 0.95, 0.99, 1.0),
)

HEARING_OUTCOME_LOW_CONFIDENCE_TOTAL = Counter(
    "justice_hearing_outcome_low_confidence_total",
    "Low-confidence hearing outcome classifications",
    ["source_name", "parser_version"],
)

HEARING_OUTCOME_OTHER_TOTAL = Counter(
    "justice_hearing_outcome_other_total",
    "Hearing outcomes classified as OTHER",
    ["source_name", "parser_version"],
)

# Required high-level ingestion KPIs
INGESTION_SUCCESS_RATE = Gauge(
    "justice_ingestion_success_rate",
    "Rolling ingestion success rate",
    ["source_name"],
)

AVG_PARSER_CONFIDENCE = Gauge(
    "justice_avg_parser_confidence",
    "Rolling average parser confidence",
    ["source_name"],
)

DUPLICATE_RATE = Gauge(
    "justice_duplicate_rate",
    "Duplicate payload rate for ingestion",
    ["source_name"],
)

RAW_BYTES_INGESTED = Counter(
    "justice_raw_bytes_ingested_total",
    "Raw bytes ingested before dedupe",
    ["source_name"],
)

ARCHIVES_MOVED = Counter(
    "justice_archives_moved_total",
    "Objects moved to warm/cold tiers",
    ["tier"],
)

_HEALTH_NUMERIC = {
    "HEALTHY": 0,
    "DEGRADED": 1,
    "FAILED": 2,
    "DISABLED": 3,
}


def record_health_gauge(source_name: str, health_status: str) -> None:
    """Push current health to the Prometheus gauge."""
    INGEST_SOURCE_HEALTH.labels(source_name=source_name).set(
        _HEALTH_NUMERIC.get(health_status, 1)
    )


def record_hearing_outcome_metrics(
    *,
    source_name: str,
    outcome_type: str,
    parser_version: str,
    confidence: float,
    verify_threshold: float,
) -> None:
    """Push hearing outcome classification metrics."""
    HEARING_OUTCOME_TOTAL.labels(
        source_name=source_name,
        outcome_type=outcome_type,
        parser_version=parser_version,
    ).inc()
    HEARING_OUTCOME_CONFIDENCE.labels(
        source_name=source_name,
        parser_version=parser_version,
    ).observe(confidence)
    if confidence < verify_threshold:
        HEARING_OUTCOME_LOW_CONFIDENCE_TOTAL.labels(
            source_name=source_name,
            parser_version=parser_version,
        ).inc()
    if outcome_type == "OTHER":
        HEARING_OUTCOME_OTHER_TOTAL.labels(
            source_name=source_name,
            parser_version=parser_version,
        ).inc()
