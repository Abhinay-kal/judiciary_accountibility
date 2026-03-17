"""Add plain-English summary fields to cases.

Revision ID: 0014_plain_english_summary_fields
Revises: 0013_investigation_snapshots
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_plain_english_summary_fields"
down_revision = "0013_investigation_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("plain_summary_short", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("plain_summary_detailed", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("summary_confidence", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("last_summary_update", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_cases_last_summary_update", "cases", ["last_summary_update"])


def downgrade() -> None:
    op.drop_index("idx_cases_last_summary_update", table_name="cases")
    op.drop_column("cases", "last_summary_update")
    op.drop_column("cases", "summary_confidence")
    op.drop_column("cases", "plain_summary_detailed")
    op.drop_column("cases", "plain_summary_short")
