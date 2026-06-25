"""Create court analytical snapshots table for batch-computed anomaly baselines.

Revision ID: 0024_court_analytical_snapshots
Revises: 0023_judge_registry_name_trgm_gin
Create Date: 2026-05-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0024_court_analytical_snapshots"
down_revision = "0023_judge_registry_name_trgm_gin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "court_analytical_snapshots",
        sa.Column("court_id", sa.Integer(), sa.ForeignKey("courts.id"), nullable=False),
        sa.Column("mean_adjournment_rate", sa.Float(), nullable=False),
        sa.Column("std_dev_adjournment_rate", sa.Float(), nullable=False),
        sa.Column("median_time_between_hearings_days", sa.Float(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("court_id"),
    )
    op.create_index(
        "idx_court_analytical_snapshots_court_id_unique",
        "court_analytical_snapshots",
        ["court_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_court_analytical_snapshots_court_id_unique", table_name="court_analytical_snapshots")
    op.drop_table("court_analytical_snapshots")