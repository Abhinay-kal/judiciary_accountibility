"""Add hearing outcome classification columns and audit log.

Revision ID: 0005_hearing_outcomes
Revises: 0004_ingestion_resilience
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_hearing_outcomes"
down_revision = "0004_ingestion_resilience"
branch_labels = None
depends_on = None


HEARING_OUTCOME_ENUM = "hearing_outcome_type"
HEARING_OUTCOME_VALUES = (
    "LISTED",
    "HEARD",
    "ADJOURNED",
    "ORDER_RESERVED",
    "DISPOSED",
    "NOT_REACHED",
    "NO_PROCEEDINGS",
    "OTHER",
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                "DO $$ BEGIN "
                "CREATE TYPE hearing_outcome_type AS ENUM "
                "('LISTED', 'HEARD', 'ADJOURNED', 'ORDER_RESERVED', 'DISPOSED', "
                "'NOT_REACHED', 'NO_PROCEEDINGS', 'OTHER'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "END $$;"
            )
        )
        outcome_type = postgresql.ENUM(
            *HEARING_OUTCOME_VALUES,
            name=HEARING_OUTCOME_ENUM,
            create_type=False,
        )
    else:
        outcome_type = sa.String(length=32)

    op.add_column("hearings", sa.Column("outcome_type", outcome_type, nullable=True))
    op.add_column("hearings", sa.Column("outcome_confidence", sa.Float(), nullable=True))
    op.add_column("hearings", sa.Column("raw_outcome_text", sa.Text(), nullable=True))
    op.add_column("hearings", sa.Column("parser_version", sa.String(length=50), nullable=True))
    op.add_column("hearings", sa.Column("annotated_by", sa.Integer(), nullable=True))
    op.add_column("hearings", sa.Column("annotated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_hearings_outcome_type", "hearings", ["outcome_type"])
    op.create_index("ix_hearings_annotated_by", "hearings", ["annotated_by"])
    op.create_index(
        "idx_hearing_outcome_date_judge",
        "hearings",
        ["outcome_type", "date", "judge_id"],
    )

    op.create_table(
        "hearing_outcome_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hearing_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("previous_outcome_type", outcome_type, nullable=True),
        sa.Column("new_outcome_type", outcome_type, nullable=True),
        sa.Column("previous_confidence", sa.Float(), nullable=True),
        sa.Column("new_confidence", sa.Float(), nullable=True),
        sa.Column("previous_parser_version", sa.String(length=50), nullable=True),
        sa.Column("new_parser_version", sa.String(length=50), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["hearing_id"], ["hearings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_hearing_outcome_audit_hearing_changed",
        "hearing_outcome_audits",
        ["hearing_id", "changed_at"],
    )
    op.create_index(
        "idx_hearing_outcome_audit_admin_changed",
        "hearing_outcome_audits",
        ["admin_id", "changed_at"],
    )

    op.execute(
        sa.text(
            """
            UPDATE hearings
            SET raw_outcome_text = COALESCE(raw_outcome_text, outcome_text),
                outcome_type = (
                    CASE
                    WHEN outcome_text IS NULL OR btrim(outcome_text) = '' THEN 'LISTED'
                    WHEN lower(outcome_text) LIKE '%adjourn%' OR lower(outcome_text) LIKE '%postponed%' OR lower(outcome_text) LIKE '%deferred%' OR lower(outcome_text) LIKE '%put up%' OR lower(outcome_text) LIKE '%relisted%' OR lower(outcome_text) LIKE '%adjd%' OR lower(outcome_text) LIKE '%adj.%' THEN 'ADJOURNED'
                    WHEN lower(outcome_text) LIKE '%order reserved%' OR lower(outcome_text) LIKE '%orders reserved%' OR lower(outcome_text) LIKE '%order kept%' THEN 'ORDER_RESERVED'
                    WHEN lower(outcome_text) LIKE '%disposed%' OR lower(outcome_text) LIKE '%dismissed%' OR lower(outcome_text) LIKE '%pronounced%' OR lower(outcome_text) LIKE '%judgment%' OR lower(outcome_text) LIKE '%allowed%' THEN 'DISPOSED'
                    WHEN lower(outcome_text) LIKE '%heard%' OR lower(outcome_text) LIKE '%considered%' OR lower(outcome_text) LIKE '%taken up%' THEN 'HEARD'
                    WHEN lower(outcome_text) LIKE '%no proceedings%' THEN 'NO_PROCEEDINGS'
                    WHEN lower(outcome_text) LIKE '%not reached%' OR lower(outcome_text) LIKE '%not taken up%' OR lower(outcome_text) LIKE '%not heard%' OR lower(outcome_text) LIKE '%case not taken%' THEN 'NOT_REACHED'
                    ELSE 'OTHER'
                    END
                )::hearing_outcome_type,
                outcome_confidence = CASE
                    WHEN outcome_text IS NULL OR btrim(outcome_text) = '' THEN 0.85
                    WHEN lower(outcome_text) LIKE '%adjourn%' OR lower(outcome_text) LIKE '%postponed%' OR lower(outcome_text) LIKE '%deferred%' OR lower(outcome_text) LIKE '%put up%' OR lower(outcome_text) LIKE '%relisted%' OR lower(outcome_text) LIKE '%adjd%' OR lower(outcome_text) LIKE '%adj.%' THEN 0.95
                    WHEN lower(outcome_text) LIKE '%disposed%' OR lower(outcome_text) LIKE '%dismissed%' OR lower(outcome_text) LIKE '%pronounced%' OR lower(outcome_text) LIKE '%judgment%' OR lower(outcome_text) LIKE '%allowed%' THEN 0.96
                    WHEN lower(outcome_text) LIKE '%order reserved%' OR lower(outcome_text) LIKE '%orders reserved%' OR lower(outcome_text) LIKE '%order kept%' THEN 0.93
                    WHEN lower(outcome_text) LIKE '%heard%' OR lower(outcome_text) LIKE '%considered%' OR lower(outcome_text) LIKE '%taken up%' THEN 0.92
                    WHEN lower(outcome_text) LIKE '%no proceedings%' OR lower(outcome_text) LIKE '%not reached%' OR lower(outcome_text) LIKE '%not taken up%' OR lower(outcome_text) LIKE '%not heard%' OR lower(outcome_text) LIKE '%case not taken%' THEN 0.90
                    ELSE 0.40
                END,
                parser_version = COALESCE(parser_version, 'outcome-rules-v1')
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_hearing_outcome_audit_admin_changed", table_name="hearing_outcome_audits")
    op.drop_index("idx_hearing_outcome_audit_hearing_changed", table_name="hearing_outcome_audits")
    op.drop_table("hearing_outcome_audits")

    op.drop_index("idx_hearing_outcome_date_judge", table_name="hearings")
    op.drop_index("ix_hearings_annotated_by", table_name="hearings")
    op.drop_index("ix_hearings_outcome_type", table_name="hearings")
    op.drop_column("hearings", "annotated_at")
    op.drop_column("hearings", "annotated_by")
    op.drop_column("hearings", "parser_version")
    op.drop_column("hearings", "raw_outcome_text")
    op.drop_column("hearings", "outcome_confidence")
    op.drop_column("hearings", "outcome_type")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS hearing_outcome_type"))