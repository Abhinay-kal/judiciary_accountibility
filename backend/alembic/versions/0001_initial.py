"""initial schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "courts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "judges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("court_id", sa.Integer(), sa.ForeignKey("courts.id"), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_uid", sa.String(length=128), nullable=False, unique=True),
        sa.Column("cnr", sa.String(length=64), nullable=True),
        sa.Column("case_number", sa.String(length=255), nullable=False),
        sa.Column("court_id", sa.Integer(), sa.ForeignKey("courts.id"), nullable=False),
        sa.Column("court_level", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("bench", sa.String(length=255), nullable=True),
        sa.Column("judges_text", sa.Text(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("next_hearing_date", sa.Date(), nullable=True),
        sa.Column("case_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_source_updated_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("case_number", "court_id", name="uq_case_number_court"),
    )

    op.create_table(
        "hearings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("judge_id", sa.Integer(), sa.ForeignKey("judges.id"), nullable=True),
        sa.Column("listing_type", sa.String(length=100), nullable=True),
        sa.Column("outcome_text", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "adjournments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("hearing_id", sa.Integer(), sa.ForeignKey("hearings.id"), nullable=True),
        sa.Column("is_adjournment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason_category", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        *_audit_columns(),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("order_link", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("raw_reference", sa.Text(), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("flag_type", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )

    op.create_table(
        "public_officials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        *_audit_columns(),
    )

    op.create_table(
        "case_party_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("party_type", sa.String(length=50), nullable=False),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("official_id", sa.Integer(), sa.ForeignKey("public_officials.id"), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
    )

    op.create_table(
        "ingestion_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_storage_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_audit_columns(),
    )

    op.create_index("ix_courts_level", "courts", ["level"])
    op.create_index("ix_courts_state", "courts", ["state"])
    op.create_index("ix_judges_name", "judges", ["name"])
    op.create_index("ix_cases_case_uid", "cases", ["case_uid"], unique=True)
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_state", "cases", ["state"])
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("idx_cases_status_state", "cases", ["status", "state"])
    op.create_index("idx_hearing_case_date", "hearings", ["case_id", "date"])
    op.create_index("idx_flags_case_type_active", "flags", ["case_id", "flag_type", "is_active"])
    op.create_index("idx_case_party_type_name", "case_party_links", ["party_type", "party_name"])
    op.create_index("idx_ingestion_source_run", "ingestion_logs", ["source", "run_id"])


def downgrade() -> None:
    op.drop_table("ingestion_logs")
    op.drop_table("case_party_links")
    op.drop_table("public_officials")
    op.drop_table("flags")
    op.drop_table("orders")
    op.drop_table("adjournments")
    op.drop_table("hearings")
    op.drop_table("cases")
    op.drop_table("judges")
    op.drop_table("courts")
