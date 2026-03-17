"""Add dormancy tracking fields to cases.

Revision ID: 0018_dormancy_case_fields
Revises: 0017_multi_tier_cache_l3_tables
Create Date: 2026-03-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_dormancy_case_fields"
down_revision = "0017_multi_tier_cache_l3_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("dormancy_status", sa.String(length=64), nullable=True))
    op.add_column("cases", sa.Column("dormancy_score", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("days_since_last_activity", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("last_activity_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("dormancy_last_updated", sa.DateTime(timezone=True), nullable=True))

    op.create_index("idx_cases_dormancy_status", "cases", ["dormancy_status"])
    op.create_index("idx_cases_dormancy_score", "cases", ["dormancy_score"])
    op.create_index("idx_cases_last_activity_date", "cases", ["last_activity_date"])
    op.create_index("idx_cases_dormancy_last_updated", "cases", ["dormancy_last_updated"])
    op.create_index("idx_cases_dormancy_status_score", "cases", ["dormancy_status", "dormancy_score"])


def downgrade() -> None:
    op.drop_index("idx_cases_dormancy_status_score", table_name="cases")
    op.drop_index("idx_cases_dormancy_last_updated", table_name="cases")
    op.drop_index("idx_cases_last_activity_date", table_name="cases")
    op.drop_index("idx_cases_dormancy_score", table_name="cases")
    op.drop_index("idx_cases_dormancy_status", table_name="cases")

    op.drop_column("cases", "dormancy_last_updated")
    op.drop_column("cases", "last_activity_date")
    op.drop_column("cases", "days_since_last_activity")
    op.drop_column("cases", "dormancy_score")
    op.drop_column("cases", "dormancy_status")
