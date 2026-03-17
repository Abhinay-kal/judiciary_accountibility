"""Add L3 precomputed cache tables and materialized views.

Revision ID: 0017_multi_tier_cache_l3_tables
Revises: 0016_field_level_provenance
Create Date: 2026-03-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_multi_tier_cache_l3_tables"
down_revision = "0016_field_level_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "court_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("court_id", sa.Integer(), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("pending_cases", sa.Integer(), nullable=False),
        sa.Column("disposed_cases", sa.Integer(), nullable=False),
        sa.Column("backlog_ratio", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_court_stats_court", "court_stats", ["court_id"])
    op.create_index("idx_court_stats_computed", "court_stats", ["computed_at"])

    op.create_table(
        "judge_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("judge_id", sa.Integer(), nullable=False),
        sa.Column("hearing_count", sa.Integer(), nullable=False),
        sa.Column("avg_outcome_confidence", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_judge_stats_judge", "judge_stats", ["judge_id"])
    op.create_index("idx_judge_stats_computed", "judge_stats", ["computed_at"])

    op.create_table(
        "state_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("pending_cases", sa.Integer(), nullable=False),
        sa.Column("avg_normalized_delay", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_state_metrics_state", "state_metrics", ["state"])
    op.create_index("idx_state_metrics_computed", "state_metrics", ["computed_at"])

    op.create_table(
        "case_type_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_type", sa.String(length=100), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("pending_cases", sa.Integer(), nullable=False),
        sa.Column("avg_delay_percentile", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_case_type_metrics_type", "case_type_metrics", ["case_type"])
    op.create_index("idx_case_type_metrics_computed", "case_type_metrics", ["computed_at"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_delay_distributions AS
            SELECT
                COALESCE(c.case_type, 'unknown') AS case_type,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY COALESCE(c.case_duration_days, 0)) AS p50_duration,
                percentile_cont(0.9) WITHIN GROUP (ORDER BY COALESCE(c.case_duration_days, 0)) AS p90_duration,
                now() AS computed_at
            FROM cases c
            WHERE c.is_deleted = false
            GROUP BY COALESCE(c.case_type, 'unknown')
            """
        )
        op.execute("CREATE INDEX IF NOT EXISTS idx_mv_delay_distributions_case_type ON mv_delay_distributions(case_type)")

        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_baseline_comparisons AS
            SELECT
                c.id AS case_id,
                c.normalized_delay,
                c.delay_percentile,
                c.baseline_level_used,
                now() AS computed_at
            FROM cases c
            WHERE c.is_deleted = false
            """
        )
        op.execute("CREATE INDEX IF NOT EXISTS idx_mv_baseline_comparisons_case_id ON mv_baseline_comparisons(case_id)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_baseline_comparisons")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_delay_distributions")

    op.drop_index("idx_case_type_metrics_computed", table_name="case_type_metrics")
    op.drop_index("idx_case_type_metrics_type", table_name="case_type_metrics")
    op.drop_table("case_type_metrics")

    op.drop_index("idx_state_metrics_computed", table_name="state_metrics")
    op.drop_index("idx_state_metrics_state", table_name="state_metrics")
    op.drop_table("state_metrics")

    op.drop_index("idx_judge_stats_computed", table_name="judge_stats")
    op.drop_index("idx_judge_stats_judge", table_name="judge_stats")
    op.drop_table("judge_stats")

    op.drop_index("idx_court_stats_computed", table_name="court_stats")
    op.drop_index("idx_court_stats_court", table_name="court_stats")
    op.drop_table("court_stats")
