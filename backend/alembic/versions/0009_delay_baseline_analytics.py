"""Add baseline-adjusted delay analytics fields and baselines table.

Revision ID: 0009_delay_baseline_analytics
Revises: 0008_case_importance_scoring
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_delay_baseline_analytics"
down_revision = "0008_case_importance_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("normalized_delay", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("delay_percentile", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("robust_z_score", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("delay_severity", sa.String(length=32), nullable=True))
    op.add_column("cases", sa.Column("baseline_level_used", sa.String(length=64), nullable=True))
    op.add_column("cases", sa.Column("baseline_sample_size", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("baseline_confidence", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("last_baseline_update", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_cases_normalized_delay", "cases", ["normalized_delay"])
    op.create_index("ix_cases_delay_severity", "cases", ["delay_severity"])
    op.create_index("ix_cases_baseline_level_used", "cases", ["baseline_level_used"])
    op.create_index("ix_cases_last_baseline_update", "cases", ["last_baseline_update"])

    op.create_table(
        "delay_baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("case_type", sa.String(length=100), nullable=True),
        sa.Column("baseline_level", sa.String(length=64), nullable=False),
        sa.Column("median_delay", sa.Float(), nullable=False),
        sa.Column("p75_delay", sa.Float(), nullable=False),
        sa.Column("p90_delay", sa.Float(), nullable=False),
        sa.Column("iqr_delay", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("window_years", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["court_id"], ["courts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "baseline_level",
            "court_id",
            "state",
            "case_type",
            name="uq_delay_baseline_level_scope",
        ),
    )
    op.create_index(
        "idx_delay_baseline_level_scope",
        "delay_baselines",
        ["baseline_level", "court_id", "state", "case_type"],
    )
    op.create_index("idx_delay_baseline_computed", "delay_baselines", ["computed_at"])
    op.create_index("idx_delay_baseline_sample", "delay_baselines", ["sample_size"])


def downgrade() -> None:
    op.drop_index("idx_delay_baseline_sample", table_name="delay_baselines")
    op.drop_index("idx_delay_baseline_computed", table_name="delay_baselines")
    op.drop_index("idx_delay_baseline_level_scope", table_name="delay_baselines")
    op.drop_table("delay_baselines")

    op.drop_index("ix_cases_last_baseline_update", table_name="cases")
    op.drop_index("ix_cases_baseline_level_used", table_name="cases")
    op.drop_index("ix_cases_delay_severity", table_name="cases")
    op.drop_index("ix_cases_normalized_delay", table_name="cases")

    op.drop_column("cases", "last_baseline_update")
    op.drop_column("cases", "baseline_confidence")
    op.drop_column("cases", "baseline_sample_size")
    op.drop_column("cases", "baseline_level_used")
    op.drop_column("cases", "delay_severity")
    op.drop_column("cases", "robust_z_score")
    op.drop_column("cases", "delay_percentile")
    op.drop_column("cases", "normalized_delay")
