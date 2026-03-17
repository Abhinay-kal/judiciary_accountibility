"""Add case_predictions table (ML module).

Revision ID: 0003_ml_predictions
Revises: 0002_scale_indexes
Create Date: 2026-03-17

This migration is safe to run on a live database.  The new table is entirely
additive — no existing columns, constraints, or indexes are modified.

Rolling back with ``alembic downgrade`` drops the table and all its indexes.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_ml_predictions"
down_revision = "0002_scale_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),

        # Prediction outputs
        sa.Column("predicted_duration_days", sa.Float(), nullable=False),
        sa.Column("lower_bound_days", sa.Float(), nullable=False),
        sa.Column("upper_bound_days", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),

        # Delay classification
        sa.Column(
            "delay_ratio", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "ml_delay_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("ml_delay_severity", sa.String(20), nullable=True),

        # Model provenance
        sa.Column("ml_model_version", sa.String(50), nullable=False),

        # Explainability
        sa.Column(
            "feature_importance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),

        # Audit columns from TimestampSoftDeleteMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_case_predictions_case_id"),
    )

    # Primary key and FK indexes
    op.create_index(
        op.f("ix_case_predictions_id"), "case_predictions", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_case_predictions_case_id"),
        "case_predictions",
        ["case_id"],
        unique=False,
    )

    # Query optimization indexes
    op.create_index(
        "idx_case_pred_flag_severity",
        "case_predictions",
        ["ml_delay_flag", "ml_delay_severity"],
    )
    op.create_index(
        "idx_case_pred_delay_ratio",
        "case_predictions",
        ["delay_ratio"],
    )


def downgrade() -> None:
    op.drop_index("idx_case_pred_delay_ratio", table_name="case_predictions")
    op.drop_index("idx_case_pred_flag_severity", table_name="case_predictions")
    op.drop_index(
        op.f("ix_case_predictions_case_id"), table_name="case_predictions"
    )
    op.drop_index(op.f("ix_case_predictions_id"), table_name="case_predictions")
    op.drop_table("case_predictions")
