"""Ingestion-specific settings.

All values read from the same .env file as the rest of the application.
Env-var names use the ``INGEST_`` prefix (pydantic-settings is
case-insensitive, so ``INGEST_FAILURE_THRESHOLD`` maps to
``ingest_failure_threshold``).

Example .env entries::

    INGEST_FAILURE_THRESHOLD=5
    INGEST_ALERT_THRESHOLD_HOURS=4
    INGEST_CONFIDENCE_MIN=0.60
    INGEST_VOLUME_ANOMALY_RATIO=0.5
    INGEST_RETRY_LIMIT=3
    INGEST_BACKOFF_BASE_SECONDS=60
    INGEST_SCHEMA_MISMATCH_THRESHOLD=0.20
    INGEST_ALERT_EMAIL_TO=ops@example.com
    INGEST_ALERT_SMTP_HOST=localhost
    INGEST_ALERT_SMTP_PORT=587
    INGEST_ALERT_WEBHOOK_URL=https://hooks.example.com/alerts
    INGEST_MAX_RAW_PAYLOAD_MB=50
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Runtime configuration for the resilient ingestion system."""

    # --- Health thresholds ---------------------------------------------------
    # Number of consecutive failures before a source is marked FAILED.
    ingest_failure_threshold: int = 5

    # Number of hours without a successful run before alerting.
    ingest_alert_threshold_hours: float = 4.0

    # Minimum acceptable parser confidence score [0,1].
    ingest_confidence_min: float = 0.60

    # Alert thresholds for classified hearing outcomes.
    ingest_outcome_other_alert_ratio: float = 0.25
    ingest_outcome_low_confidence_alert_ratio: float = 0.20
    ingest_judge_missing_alert_ratio: float = 0.15
    ingest_judge_low_confidence_alert_ratio: float = 0.20

    # Fraction deviation from rolling-median record count that triggers anomaly.
    # e.g. 0.5 means ±50 % of median.
    ingest_volume_anomaly_ratio: float = 0.50

    # Maximum automated retries before giving up on a run.
    ingest_retry_limit: int = 3

    # Base backoff in seconds for exponential retry sleep (multiplied by 2^n).
    ingest_backoff_base_seconds: int = 60

    # Fraction of new/missing keys that classifies a payload as schema-changed.
    ingest_schema_mismatch_threshold: float = 0.20

    # --- Raw payload storage ------------------------------------------------
    # Maximum size in MB allowed for a single stored raw payload.
    ingest_max_raw_payload_mb: int = 50

    # Directory for raw payload storage (relative to working directory).
    ingest_raw_storage_dir: str = "raw_data"

    # --- Checkpoint storage -------------------------------------------------
    # Directory for run checkpoint files.
    ingest_checkpoint_dir: str = "raw_data/checkpoints"

    # --- Alert channels -----------------------------------------------------
    # Comma-separated recipient addresses for email alerts.  Empty → disabled.
    ingest_alert_email_to: str = ""

    # SMTP settings (standard mail relay, e.g. local Postfix or SMTP server).
    ingest_alert_smtp_host: str = "localhost"
    ingest_alert_smtp_port: int = 25
    ingest_alert_smtp_user: str = ""
    ingest_alert_smtp_password: str = ""
    ingest_alert_smtp_from: str = "noreply@justice-tracker.local"
    ingest_alert_smtp_tls: bool = False

    # Webhook URL for Slack / Teams / custom HTTP alerting.  Empty → disabled.
    ingest_alert_webhook_url: str = ""

    # --- Dynamic scheduling --------------------------------------------------
    # How many minutes the dynamic scheduler sleeps between scheduling sweeps.
    ingest_scheduler_interval_minutes: int = 5

    # Feature flags
    delta_fetch_enabled: bool = True
    cas_enabled: bool = True
    manual_ingest_enabled: bool = True

    # Lifecycle windows
    lifecycle_hot_days: int = 30
    lifecycle_warm_days: int = 90

    # Alerting / re-alert suppression
    ingest_alert_hours: int = 24
    ingest_realert_base_minutes: int = 30
    ingest_realert_max_minutes: int = 720

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    """Return a cached IngestionSettings instance."""
    return IngestionSettings()
