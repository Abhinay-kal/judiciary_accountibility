"""
Resilient Ingestion Architecture
==================================

A production-grade ingestion subsystem that guarantees:
  - No silent failures
  - Per-source health state machine (HEALTHY/DEGRADED/FAILED/DISABLED)
  - Schema-change, volume-anomaly, and parser-confidence detection
  - Multi-channel alerting via SMTP, webhook, or escalated logging
  - Manual operator overrides (pause/resume/force-run/file-upload)
  - Incremental exponential-backoff retry with checkpoint recovery
  - Dynamic Celery scheduling based on source priority and health
  - Full Prometheus observability

Sub-modules
-----------
models      — SQLAlchemy ORM: IngestionSource, IngestionRun
config      — IngestionSettings (INGEST_ env prefix)
metrics     — Prometheus counters/histograms for ingestion ops
health      — Health-state machine and update logic
detectors/  — schema_change, volume_anomaly, parser_confidence
pipeline    — Main ResilientIngestionPipeline
alerts      — Alert manager (SMTP, webhook, log escalation)
monitor     — Cross-source monitoring sweep
manual      — Operator API helpers (pause/resume/upload)
recovery    — Retry / reprocessing logic
scheduler   — Dynamic Celery beat scheduling
"""
