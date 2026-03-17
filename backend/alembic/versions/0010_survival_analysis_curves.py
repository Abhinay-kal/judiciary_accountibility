"""Add survival-analysis case fields and survival_curves table.

Revision ID: 0010_survival_analysis_curves
Revises: 0009_delay_baseline_analytics
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_survival_analysis_curves"
down_revision = "0009_delay_baseline_analytics"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()

    op.add_column("cases", sa.Column("case_duration_days", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("is_disposed", sa.Boolean(), nullable=True))
    op.create_index("ix_cases_case_duration_days", "cases", ["case_duration_days"])
    op.create_index("ix_cases_is_disposed", "cases", ["is_disposed"])

    op.create_table(
        "survival_curves",
        sa.Column("curve_id", sa.Integer(), nullable=False),
        sa.Column("grouping_type", sa.String(length=64), nullable=False),
        sa.Column("grouping_value", sa.String(length=255), nullable=False),
        sa.Column("case_type", sa.String(length=100), nullable=True),
        sa.Column("time_points", json_type, nullable=False),
        sa.Column("survival_probabilities", json_type, nullable=False),
        sa.Column("lower_ci", json_type, nullable=False),
        sa.Column("upper_ci", json_type, nullable=False),
        sa.Column("hazard_rates", json_type, nullable=False),
        sa.Column("median_time", sa.Float(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("curve_id"),
        sa.UniqueConstraint("grouping_type", "grouping_value", "case_type", name="uq_survival_curve_group"),
    )
    op.create_index("idx_survival_curve_group", "survival_curves", ["grouping_type", "grouping_value", "case_type"])
    op.create_index("idx_survival_curve_computed", "survival_curves", ["computed_at"])


def downgrade() -> None:
    op.drop_index("idx_survival_curve_computed", table_name="survival_curves")
    op.drop_index("idx_survival_curve_group", table_name="survival_curves")
    op.drop_table("survival_curves")

    op.drop_index("ix_cases_is_disposed", table_name="cases")
    op.drop_index("ix_cases_case_duration_days", table_name="cases")
    op.drop_column("cases", "is_disposed")
    op.drop_column("cases", "case_duration_days")
