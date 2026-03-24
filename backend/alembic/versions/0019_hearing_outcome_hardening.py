"""Harden hearing outcome schema safety constraints.

Revision ID: 0019_hearing_outcome_hardening
Revises: 0018_dormancy_case_fields
Create Date: 2026-03-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_hearing_outcome_hardening"
down_revision = "0018_dormancy_case_fields"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _constraint_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name) if constraint.get("name")}


def upgrade() -> None:
    columns = _column_names("hearings")
    indexes = _index_names("hearings")

    if "outcome_type" not in columns:
        bind = op.get_bind()
        if bind.dialect.name == "postgresql":
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
            op.add_column(
                "hearings",
                sa.Column(
                    "outcome_type",
                    sa.Enum(
                        "LISTED",
                        "HEARD",
                        "ADJOURNED",
                        "ORDER_RESERVED",
                        "DISPOSED",
                        "NOT_REACHED",
                        "NO_PROCEEDINGS",
                        "OTHER",
                        name="hearing_outcome_type",
                    ),
                    nullable=True,
                ),
            )
        else:
            op.add_column("hearings", sa.Column("outcome_type", sa.String(length=32), nullable=True))

    if "outcome_confidence" not in columns:
        op.add_column("hearings", sa.Column("outcome_confidence", sa.Float(), nullable=True))
    if "raw_outcome_text" not in columns:
        op.add_column("hearings", sa.Column("raw_outcome_text", sa.Text(), nullable=True))
    if "parser_version" not in columns:
        op.add_column("hearings", sa.Column("parser_version", sa.String(length=50), nullable=True))
    if "annotated_by" not in columns:
        op.add_column("hearings", sa.Column("annotated_by", sa.Integer(), nullable=True))
    if "annotated_at" not in columns:
        op.add_column("hearings", sa.Column("annotated_at", sa.DateTime(timezone=True), nullable=True))

    if "idx_hearing_outcome_date_judge" not in indexes:
        op.create_index("idx_hearing_outcome_date_judge", "hearings", ["outcome_type", "date", "judge_id"])

    if "ix_hearings_outcome_type" not in indexes:
        op.create_index("ix_hearings_outcome_type", "hearings", ["outcome_type"])

    constraints = _constraint_names("hearings")
    constraint_name = "ck_hearings_outcome_confidence_range"
    if constraint_name not in constraints:
        op.create_check_constraint(
            constraint_name,
            "hearings",
            "outcome_confidence IS NULL OR (outcome_confidence >= 0.0 AND outcome_confidence <= 1.0)",
        )


def downgrade() -> None:
    indexes = _index_names("hearings")
    if "ix_hearings_outcome_type" in indexes:
        op.drop_index("ix_hearings_outcome_type", table_name="hearings")

    constraints = _constraint_names("hearings")
    constraint_name = "ck_hearings_outcome_confidence_range"
    if constraint_name in constraints:
        op.drop_constraint(constraint_name, "hearings", type_="check")
