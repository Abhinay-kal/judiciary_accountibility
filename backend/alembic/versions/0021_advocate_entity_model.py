"""Add advocate entity model and interim application tracking.

Revision ID: 0021_advocate_entity_model
Revises: 0020_population_runs
Create Date: 2026-03-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_advocate_entity_model"
down_revision = "0020_population_runs"
branch_labels = None
depends_on = None
NOW_DEFAULT = sa.text("now()")


def upgrade() -> None:
    # Create advocates table
    op.create_table(
        "advocates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("advocate_uid", sa.String(length=128), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("name_variants", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("phonetic_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("bar_council_id", sa.String(length=100), nullable=True),
        sa.Column("bar_council_name", sa.String(length=255), nullable=True),
        sa.Column("enrollment_number", sa.String(length=100), nullable=True),
        sa.Column("enrollment_date", sa.Date(), nullable=True),
        sa.Column("primary_court_id", sa.Integer(), nullable=True),
        sa.Column("practice_states", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_adjournment_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_adjournment_rate", sa.Float(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verification_source", sa.String(length=100), nullable=True),
        sa.Column("last_seen_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["primary_court_id"], ["courts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advocate_uid", name="uq_advocates_uid"),
    )
    op.create_index("idx_advocates_bar_council_id", "advocates", ["bar_council_id"])
    op.create_index("idx_advocates_canonical_name", "advocates", ["canonical_name"])
    op.create_index("idx_advocates_is_verified", "advocates", ["is_verified"])

    # Create case_counsel table (many-to-many linking cases to advocates)
    op.create_table(
        "case_counsel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("advocate_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),  # PETITIONER, RESPONDENT, INTERVENER, AMICUS, OTHER
        sa.Column("first_appearance_date", sa.Date(), nullable=True),
        sa.Column("last_appearance_date", sa.Date(), nullable=True),
        sa.Column("is_currently_appearing", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("adjournment_requests_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hearings_attended", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hearings_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["advocate_id"], ["advocates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "advocate_id", "role", name="uq_case_advocate_role"),
    )
    op.create_index("idx_case_counsel_advocate", "case_counsel", ["advocate_id"])
    op.create_index("idx_case_counsel_appearance_date", "case_counsel", ["first_appearance_date"])
    op.create_index("idx_case_counsel_case", "case_counsel", ["case_id"])

    # Create interim_applications table
    op.create_table(
        "interim_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("application_type", sa.String(length=50), nullable=False),  # BAIL, STAY_OF_PROCEEDINGS, etc.
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("applicant_advocate_id", sa.Integer(), nullable=True),
        sa.Column("applicant_party_role", sa.String(length=100), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("decision_status", sa.String(length=50), nullable=True),  # GRANTED, REJECTED, DISMISSED, RESERVED
        sa.Column("decision_order_id", sa.Integer(), nullable=True),
        sa.Column("is_frivolous_indicator", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("grounds_cited_text", sa.Text(), nullable=True),
        sa.Column("urgency_claim_text", sa.Text(), nullable=True),
        sa.Column("delay_caused_days", sa.Integer(), nullable=True),
        sa.Column("related_adjournment_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW_DEFAULT),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["applicant_advocate_id"], ["advocates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decision_order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_interim_case_filing_date", "interim_applications", ["case_id", "filing_date"])
    op.create_index("idx_interim_case_status", "interim_applications", ["case_id", "decision_status"])
    op.create_index("idx_interim_type", "interim_applications", ["application_type"])

    # Alter adjournments table to add new fields (using raw SQL to handle idempotency)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='adjournments' AND column_name='reason_type') THEN
            ALTER TABLE adjournments ADD COLUMN reason_type VARCHAR(50) NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='adjournments' AND column_name='requested_by') THEN
            ALTER TABLE adjournments ADD COLUMN requested_by INTEGER NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='adjournments' AND column_name='was_contested') THEN
            ALTER TABLE adjournments ADD COLUMN was_contested BOOLEAN NOT NULL DEFAULT false;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='adjournments' AND column_name='grounds_cited_text') THEN
            ALTER TABLE adjournments ADD COLUMN grounds_cited_text TEXT NULL;
        END IF;
    END $$;
    """)
    
    # Add foreign key if it doesn't exist
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                      WHERE constraint_name = 'fk_adjournments_requested_by') THEN
            ALTER TABLE adjournments ADD CONSTRAINT fk_adjournments_requested_by 
                FOREIGN KEY (requested_by) REFERENCES advocates(id) ON DELETE SET NULL;
        END IF;
    END $$;
    """)
    
    # Add indexes if they don't exist
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_adjournments_reason_type') THEN
            CREATE INDEX idx_adjournments_reason_type ON adjournments(reason_type);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_adjournments_requested_by') THEN
            CREATE INDEX idx_adjournments_requested_by ON adjournments(requested_by);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Drop adjournments alterations
    op.drop_index("idx_adjournments_requested_by", table_name="adjournments")
    op.drop_index("idx_adjournments_reason_type", table_name="adjournments")
    op.drop_constraint("fk_adjournments_requested_by", "adjournments", type_="foreignkey")
    op.drop_column("adjournments", "grounds_cited_text")
    op.drop_column("adjournments", "was_contested")
    op.drop_column("adjournments", "requested_by")
    op.drop_column("adjournments", "reason_type")

    # Drop interim_applications table
    op.drop_index("idx_interim_type", table_name="interim_applications")
    op.drop_index("idx_interim_case_status", table_name="interim_applications")
    op.drop_index("idx_interim_case_filing_date", table_name="interim_applications")
    op.drop_table("interim_applications")

    # Drop case_counsel table
    op.drop_index("idx_case_counsel_case", table_name="case_counsel")
    op.drop_index("idx_case_counsel_appearance_date", table_name="case_counsel")
    op.drop_index("idx_case_counsel_advocate", table_name="case_counsel")
    op.drop_table("case_counsel")

    # Drop advocates table
    op.drop_index("idx_advocates_is_verified", table_name="advocates")
    op.drop_index("idx_advocates_canonical_name", table_name="advocates")
    op.drop_index("idx_advocates_bar_council_id", table_name="advocates")
    op.drop_table("advocates")
