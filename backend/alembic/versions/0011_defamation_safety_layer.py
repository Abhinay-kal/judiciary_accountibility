"""Add defamation-safe moderation and correction workflow tables.

Revision ID: 0011_defamation_safety_layer
Revises: 0010_survival_analysis_curves
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_defamation_safety_layer"
down_revision = "0010_survival_analysis_curves"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()

    target_type_enum = sa.Enum("case", "flag", "evidence", "hearing", name="moderation_target_type", native_enum=False)
    label_enum = sa.Enum(
        "UNVERIFIED",
        "VERIFIED",
        "DATA_ANOMALY",
        "UNUSUAL_DELAY_PATTERN",
        "REQUIRES_VERIFICATION",
        "SENSITIVE",
        "REMOVED",
        "LEGALLY_RESTRICTED",
        name="content_label_kind",
        native_enum=False,
    )
    label_source_enum = sa.Enum("automated", "manual", name="content_label_source", native_enum=False)
    correction_status_enum = sa.Enum(
        "PENDING",
        "IN_REVIEW",
        "ACCEPTED",
        "REJECTED",
        "ESCALATED",
        name="correction_request_status",
        native_enum=False,
    )
    moderation_action_enum = sa.Enum(
        "LABEL_ADDED",
        "LABEL_REMOVED",
        "CORRECTION_HANDLED",
        "CONTENT_REDACED",
        "TAKEDOWN",
        name="moderation_action_type",
        native_enum=False,
    )
    public_status_enum = sa.Enum("PUBLIC", "LIMITED", "HIDDEN", name="public_visibility_status", native_enum=False)

    op.create_table(
        "content_labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_type", target_type_enum, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("label", label_enum, nullable=False),
        sa.Column("label_source", label_source_enum, nullable=False, server_default="automated"),
        sa.Column("label_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_content_labels_target", "content_labels", ["target_type", "target_id"])
    op.create_index("idx_content_labels_label", "content_labels", ["label", "created_at"])

    op.create_table(
        "correction_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_type", target_type_enum, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("requester_name", sa.String(length=255), nullable=False),
        sa.Column("requester_contact", sa.String(length=255), nullable=False),
        sa.Column("requester_affiliation", sa.String(length=255), nullable=True),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("evidence_upload_ref", sa.Text(), nullable=True),
        sa.Column("status", correction_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("assigned_admin", sa.Integer(), nullable=True),
        sa.Column("review_notes", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_corrections_target", "correction_requests", ["target_type", "target_id", "submitted_at"])
    op.create_index("idx_corrections_status", "correction_requests", ["status", "submitted_at"])

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_type", moderation_action_enum, nullable=False),
        sa.Column("target_type", target_type_enum, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_moderation_logs_target", "moderation_logs", ["target_type", "target_id", "created_at"])
    op.create_index("idx_moderation_logs_action", "moderation_logs", ["action_type", "created_at"])

    for table_name in ("cases", "flags", "orders"):
        op.add_column(table_name, sa.Column("public_status", public_status_enum, nullable=False, server_default="PUBLIC"))
        op.add_column(table_name, sa.Column("public_note", sa.Text(), nullable=True))
        op.add_column(table_name, sa.Column("last_label_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table_name, sa.Column("last_label_id", sa.Integer(), nullable=True))
        op.create_index(f"idx_{table_name}_public_status", table_name, ["public_status"])


def downgrade() -> None:
    for table_name in ("orders", "flags", "cases"):
        op.drop_index(f"idx_{table_name}_public_status", table_name=table_name)
        op.drop_column(table_name, "last_label_id")
        op.drop_column(table_name, "last_label_at")
        op.drop_column(table_name, "public_note")
        op.drop_column(table_name, "public_status")

    op.drop_index("idx_moderation_logs_action", table_name="moderation_logs")
    op.drop_index("idx_moderation_logs_target", table_name="moderation_logs")
    op.drop_table("moderation_logs")

    op.drop_index("idx_corrections_status", table_name="correction_requests")
    op.drop_index("idx_corrections_target", table_name="correction_requests")
    op.drop_table("correction_requests")

    op.drop_index("idx_content_labels_label", table_name="content_labels")
    op.drop_index("idx_content_labels_target", table_name="content_labels")
    op.drop_table("content_labels")
