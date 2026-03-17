"""Add ingestion_sources and ingestion_runs tables (Resilient Ingestion module).

Revision ID: 0004_ingestion_resilience
Revises: 0003_ml_predictions
Create Date: 2026-03-17

This migration is fully additive — no existing tables or columns are modified.
Roll back with ``alembic downgrade 0003_ml_predictions`` to drop both tables.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_ingestion_resilience"
down_revision = "0003_ml_predictions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ingestion_sources
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="HTML"),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("expected_update_interval_minutes", sa.Integer(), nullable=True),
        # Health tracking
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=True),
        sa.Column("last_record_count", sa.Integer(), nullable=True),
        sa.Column("expected_record_count", sa.Integer(), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=True),
        sa.Column(
            "health_status",
            sa.String(length=20),
            nullable=False,
            server_default="HEALTHY",
        ),
        # JSON blobs
        sa.Column(
            "mirror_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "schema_baseline",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Audit timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", name="uq_ingestion_source_name"),
    )
    op.create_index(
        "idx_ingestion_sources_health_active",
        "ingestion_sources",
        ["health_status", "is_active"],
    )

    # ------------------------------------------------------------------
    # ingestion_runs
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        # Timing
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RUNNING"),
        # Record counts
        sa.Column("records_fetched", sa.Integer(), nullable=True),
        sa.Column("records_parsed", sa.Integer(), nullable=True),
        sa.Column("records_inserted", sa.Integer(), nullable=True),
        sa.Column("records_failed", sa.Integer(), nullable=True),
        # HTTP
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        # Raw storage
        sa.Column("raw_payload_location", sa.Text(), nullable=True),
        # QA signals
        sa.Column("parser_confidence_score", sa.Float(), nullable=True),
        sa.Column("schema_change_detected", sa.Boolean(), nullable=True),
        sa.Column("volume_anomaly_detected", sa.Boolean(), nullable=True),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Constraints / FK
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_ingestion_run_id"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["ingestion_sources.id"],
            ondelete="CASCADE",
            name="fk_ingestion_runs_source_id",
        ),
    )
    op.create_index(
        "idx_ingestion_runs_source_started",
        "ingestion_runs",
        ["source_id", "started_at"],
    )
    op.create_index(
        "idx_ingestion_runs_status",
        "ingestion_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("ingestion_sources")
