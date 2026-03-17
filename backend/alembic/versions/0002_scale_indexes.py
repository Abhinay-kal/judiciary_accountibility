"""add scale indexes

Revision ID: 0002_scale_indexes
Revises: 0001_initial
Create Date: 2026-03-17
"""

from alembic import op


revision = "0002_scale_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_cases_court_status_next_hearing", "cases", ["court_id", "status", "next_hearing_date"])
    op.create_index("idx_cases_state_case_type_filing", "cases", ["state", "case_type", "filing_date"])
    op.create_index("idx_hearing_judge_date", "hearings", ["judge_id", "date"])
    op.create_index("idx_adjournments_case_is_adj", "adjournments", ["case_id", "is_adjournment"])
    op.create_index("idx_flags_type_active_created", "flags", ["flag_type", "is_active", "created_at"])
    op.create_index("idx_case_party_official_verified", "case_party_links", ["official_id", "is_verified"])
    op.create_index("idx_ingestion_created_at", "ingestion_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_ingestion_created_at", table_name="ingestion_logs")
    op.drop_index("idx_case_party_official_verified", table_name="case_party_links")
    op.drop_index("idx_flags_type_active_created", table_name="flags")
    op.drop_index("idx_adjournments_case_is_adj", table_name="adjournments")
    op.drop_index("idx_hearing_judge_date", table_name="hearings")
    op.drop_index("idx_cases_state_case_type_filing", table_name="cases")
    op.drop_index("idx_cases_court_status_next_hearing", table_name="cases")
