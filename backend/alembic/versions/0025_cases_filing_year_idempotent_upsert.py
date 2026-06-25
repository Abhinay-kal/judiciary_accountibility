"""Add filing_year and unique key for idempotent case bulk upsert.

Revision ID: 0025_cases_filing_year_idempotent_upsert
Revises: 0024_court_analytical_snapshots
Create Date: 2026-05-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0025_cases_filing_year_idempotent_upsert"
down_revision = "0024_court_analytical_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("filing_year", sa.Integer(), nullable=True, server_default="0"))

    op.execute(
        sa.text(
            """
            UPDATE cases
            SET filing_year = COALESCE(EXTRACT(YEAR FROM filing_date)::integer, 0)
            """
        )
    )

    op.alter_column("cases", "filing_year", nullable=False, server_default=None)
    op.create_unique_constraint(
        "uq_case_number_filing_year",
        "cases",
        ["case_number", "filing_year"],
    )
    op.drop_constraint("uq_case_number_court", "cases", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_case_number_court",
        "cases",
        ["case_number", "court_id"],
    )
    op.drop_constraint("uq_case_number_filing_year", "cases", type_="unique")
    op.drop_column("cases", "filing_year")