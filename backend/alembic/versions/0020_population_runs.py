"""Add population run tracking tables.

Revision ID: 0020_population_runs
Revises: 0019_hearing_outcome_hardening
Create Date: 2026-03-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_population_runs"
down_revision = "0019_hearing_outcome_hardening"
branch_labels = None
depends_on = None
NOW_DEFAULT = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "population_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="QUEUED"),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("root_task_id", sa.String(length=64), nullable=True),
        sa.Column("total_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_population_runs_run_id"),
    )
    op.create_index("idx_population_runs_status_started", "population_runs", ["status", "started_at"])
    op.create_index("idx_population_runs_trigger_started", "population_runs", ["trigger_type", "started_at"])
    op.create_index(op.f("ix_population_runs_admin_id"), "population_runs", ["admin_id"], unique=False)
    op.create_index(op.f("ix_population_runs_root_task_id"), "population_runs", ["root_task_id"], unique=False)

    op.create_table(
        "population_source_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("population_run_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="QUEUED"),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["population_run_id"], ["population_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["ingestion_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_population_source_runs_run_status", "population_source_runs", ["population_run_id", "status"])
    op.create_index("idx_population_source_runs_source", "population_source_runs", ["source_id"])
    op.create_index(op.f("ix_population_source_runs_task_id"), "population_source_runs", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_population_source_runs_task_id"), table_name="population_source_runs")
    op.drop_index("idx_population_source_runs_source", table_name="population_source_runs")
    op.drop_index("idx_population_source_runs_run_status", table_name="population_source_runs")
    op.drop_table("population_source_runs")

    op.drop_index(op.f("ix_population_runs_root_task_id"), table_name="population_runs")
    op.drop_index(op.f("ix_population_runs_admin_id"), table_name="population_runs")
    op.drop_index("idx_population_runs_trigger_started", table_name="population_runs")
    op.drop_index("idx_population_runs_status_started", table_name="population_runs")
    op.drop_table("population_runs")
