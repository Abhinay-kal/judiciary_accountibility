"""SQLAlchemy ORM models for the resilient ingestion subsystem.

Two new tables:

``ingestion_sources``
    One row per external judicial data source.  Tracks lifecycle state,
    health, failure counters, and per-source configuration.

``ingestion_runs``
    Append-only log of every ingestion attempt.  Referenced by the
    pipeline, recovery system, and admin API.

These models live alongside the existing ``IngestionLog`` (which records
individual *record-level* outcomes); the new tables focus on *run-level*
and *source-level* state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ---------------------------------------------------------------------------
# Health status enum values (stored as plain strings for readability)
# ---------------------------------------------------------------------------

HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_FAILED = "FAILED"
HEALTH_DISABLED = "DISABLED"

# Run status values
RUN_SUCCESS = "SUCCESS"
RUN_PARTIAL = "PARTIAL"
RUN_FAILED = "FAILED"

POPULATION_QUEUED = "QUEUED"
POPULATION_RUNNING = "RUNNING"
POPULATION_SUCCESS = "SUCCESS"
POPULATION_PARTIAL = "PARTIAL"
POPULATION_FAILED = "FAILED"

POPULATION_TRIGGER_MANUAL = "MANUAL"
POPULATION_TRIGGER_SCHEDULED = "SCHEDULED"

# Valid source types
SOURCE_HTML = "HTML"
SOURCE_JSON = "JSON"
SOURCE_PDF = "PDF"
SOURCE_API = "API"
SOURCE_SCRAPER = "SCRAPER"
INGESTION_SOURCE_FK = "ingestion_sources.id"


class IngestionSource(Base):
    """Represents a single external judicial data source.

    The health state machine transitions are managed by
    :mod:`app.ingestion.health`.
    """

    __tablename__ = "ingestion_sources"
    __table_args__ = (
        UniqueConstraint("source_name", name="uq_ingestion_source_name"),
        Index("idx_ingestion_sources_health_active", "health_status", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # HTML/JSON/PDF/API/SCRAPER
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False, index=True)

    # Scheduling
    expected_update_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=1440, nullable=False
    )

    # Timing
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Failure tracking
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Performance
    avg_response_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Parser info
    parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Health state (HEALTHY/DEGRADED/FAILED/DISABLED)
    health_status: Mapped[str] = mapped_column(
        String(20), default=HEALTH_HEALTHY, nullable=False, index=True
    )

    # Mirror / fallback URLs stored as a JSON list
    mirror_urls: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Extra per-source configuration (headers, selectors, etc.)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Baseline schema snapshot for change detection (JSON)
    schema_baseline: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    runs: Mapped[list["IngestionRun"]] = relationship(
        back_populates="source",
        order_by="IngestionRun.started_at.desc()",
    )


class IngestionRun(Base):
    """Immutable append-only record of a single ingestion run attempt.

    Rows are never updated after creation (except ``finished_at`` and
    ``status`` which are written on completion).
    """

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("idx_ingestion_runs_source_started", "source_id", "started_at"),
        Index("idx_ingestion_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey(INGESTION_SOURCE_FK), nullable=False, index=True
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Outcome
    status: Mapped[str] = mapped_column(
        String(20), default=RUN_FAILED, nullable=False
    )

    # Record stats
    records_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_parsed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Network
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Diagnosis
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    raw_object_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parser_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    schema_change_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    volume_anomaly_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Rich diagnostics (schema diff, confidence breakdown, etc.)
    diagnostics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    provenance_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    source: Mapped["IngestionSource"] = relationship(back_populates="runs")
    raw_payloads: Mapped[list["RawPayload"]] = relationship(back_populates="ingestion_run")


class RawPayload(Base):
    """Content-addressed raw payload storage metadata."""

    __tablename__ = "raw_payloads"
    __table_args__ = (
        UniqueConstraint("checksum", name="uq_raw_payloads_checksum"),
        Index("idx_raw_payloads_source_retrieved", "source_id", "retrieved_at"),
        Index("idx_raw_payloads_ingestion_run", "ingestion_run_id"),
    )

    payload_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_id: Mapped[int] = mapped_column(ForeignKey(INGESTION_SOURCE_FK), nullable=False, index=True)
    ingestion_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_runs.id"), nullable=True, index=True
    )
    provenance_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    source: Mapped["IngestionSource"] = relationship()
    ingestion_run: Mapped[Optional["IngestionRun"]] = relationship(back_populates="raw_payloads")


class PopulationRun(Base):
    """Tracks a parent population run across all active ingestion sources."""

    __tablename__ = "population_runs"
    __table_args__ = (
        Index("idx_population_runs_status_started", "status", "started_at"),
        Index("idx_population_runs_trigger_started", "trigger_type", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default=POPULATION_TRIGGER_MANUAL)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=POPULATION_QUEUED, index=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    total_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    diagnostics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_runs: Mapped[list["PopulationSourceRun"]] = relationship(
        back_populates="population_run",
        order_by="PopulationSourceRun.id.asc()",
        cascade="all, delete-orphan",
    )


class PopulationSourceRun(Base):
    """Tracks source-level progress and diagnostics for one population run."""

    __tablename__ = "population_source_runs"
    __table_args__ = (
        Index("idx_population_source_runs_run_status", "population_run_id", "status"),
        Index("idx_population_source_runs_source", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    population_run_id: Mapped[int] = mapped_column(
        ForeignKey("population_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey(INGESTION_SOURCE_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=POPULATION_QUEUED, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnostics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    population_run: Mapped["PopulationRun"] = relationship(back_populates="source_runs")
    source: Mapped["IngestionSource"] = relationship()
