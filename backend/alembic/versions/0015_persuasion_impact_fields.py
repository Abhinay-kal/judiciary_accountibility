"""Add persuasion impact fields to cases.

Revision ID: 0015_persuasion_impact_fields
Revises: 0014_plain_english_summary_fields
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_persuasion_impact_fields"
down_revision = "0014_plain_english_summary_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("impact_headline", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("impact_summary", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("impact_confidence", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("impact_last_updated", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_cases_impact_last_updated", "cases", ["impact_last_updated"])


def downgrade() -> None:
    op.drop_index("idx_cases_impact_last_updated", table_name="cases")
    op.drop_column("cases", "impact_last_updated")
    op.drop_column("cases", "impact_confidence")
    op.drop_column("cases", "impact_summary")
    op.drop_column("cases", "impact_headline")
