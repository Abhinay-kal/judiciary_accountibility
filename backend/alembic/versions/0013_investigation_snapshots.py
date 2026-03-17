"""Add investigation snapshots for shareable investigation pages.

Revision ID: 0013_investigation_snapshots
Revises: 0012_right_to_respond_feedback
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_investigation_snapshots"
down_revision = "0012_right_to_respond_feedback"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "investigation_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("data_cutoff_date", sa.Date(), nullable=True),
        sa.Column("snapshot_data", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("case_id", "version_number", name="uq_investigation_snapshot_case_version"),
    )
    op.create_index(
        "idx_investigation_snapshot_case_current",
        "investigation_snapshots",
        ["case_id", "is_current"],
    )
    op.create_index(
        "idx_investigation_snapshot_generated",
        "investigation_snapshots",
        ["generated_at"],
    )
    op.create_index(
        "idx_investigation_snapshot_hash",
        "investigation_snapshots",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_investigation_snapshot_hash", table_name="investigation_snapshots")
    op.drop_index("idx_investigation_snapshot_generated", table_name="investigation_snapshots")
    op.drop_index("idx_investigation_snapshot_case_current", table_name="investigation_snapshots")
    op.drop_table("investigation_snapshots")
