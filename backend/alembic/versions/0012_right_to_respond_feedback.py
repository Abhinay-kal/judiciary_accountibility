"""Add right-to-respond feedback workflow tables.

Revision ID: 0012_right_to_respond_feedback
Revises: 0011_defamation_safety_layer
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_right_to_respond_feedback"
down_revision = "0011_defamation_safety_layer"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()

    responder_type_enum = sa.Enum(
        "INDIVIDUAL",
        "GOV_AGENCY",
        "COMPANY",
        "LAW_FIRM",
        "NGO",
        name="feedback_responder_type",
        native_enum=False,
    )
    verification_method_enum = sa.Enum(
        "email_token",
        "domain_verification",
        "letter_of_authority",
        "admin_verified",
        "oauth_provider",
        name="feedback_verification_method",
        native_enum=False,
    )
    received_via_enum = sa.Enum(
        "API",
        "WEB",
        "UPLOAD",
        name="feedback_received_via",
        native_enum=False,
    )
    public_status_enum = sa.Enum(
        "PENDING_REVIEW",
        "PUBLISHED",
        "REJECTED",
        "LIMITED",
        name="feedback_public_status",
        native_enum=False,
    )
    display_label_enum = sa.Enum(
        "OFFICIAL_RESPONSE",
        "RESPONSE_FROM_PARTY",
        "CLARIFICATION",
        name="feedback_display_label",
        native_enum=False,
    )
    audit_action_enum = sa.Enum(
        "submitted",
        "verified",
        "published",
        "rejected",
        "limited",
        "escalated",
        "edited_by_admin",
        "deleted",
        "urgent_hidden",
        name="feedback_audit_action",
        native_enum=False,
    )

    op.create_table(
        "case_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("responder_type", responder_type_enum, nullable=False),
        sa.Column("responder_name", sa.Text(), nullable=False),
        sa.Column("responder_affiliation", sa.Text(), nullable=True),
        sa.Column("responder_contact", sa.Text(), nullable=False),
        sa.Column("responder_contact_hash", sa.String(length=128), nullable=False),
        sa.Column("responder_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("responder_verification_method", verification_method_enum, nullable=True),
        sa.Column("verification_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_text_index", sa.Text(), nullable=True),
        sa.Column("attachments_ref", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("received_via", received_via_enum, nullable=False, server_default="WEB"),
        sa.Column("public_status", public_status_enum, nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("public_note", sa.Text(), nullable=True),
        sa.Column("display_label", display_label_enum, nullable=False, server_default="RESPONSE_FROM_PARTY"),
        sa.Column("moderator_id", sa.Integer(), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderation_notes", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("legal_escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("urgent_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("loa_attachment_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_case_feedback_case_status_submitted", "case_feedback", ["case_id", "public_status", "submitted_at"])
    op.create_index("idx_case_feedback_contact_hash_submitted", "case_feedback", ["responder_contact_hash", "submitted_at"])

    op.create_table(
        "feedback_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("method", verification_method_enum, nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verifier_admin_id", sa.Integer(), nullable=True),
        sa.Column("metadata", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["feedback_id"], ["case_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_feedback_verification_feedback", "feedback_verifications", ["feedback_id", "method"])

    op.create_table(
        "feedback_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("action", audit_action_enum, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["feedback_id"], ["case_feedback.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_feedback_audit_feedback_created", "feedback_audit_logs", ["feedback_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_feedback_audit_feedback_created", table_name="feedback_audit_logs")
    op.drop_table("feedback_audit_logs")

    op.drop_index("idx_feedback_verification_feedback", table_name="feedback_verifications")
    op.drop_table("feedback_verifications")

    op.drop_index("idx_case_feedback_contact_hash_submitted", table_name="case_feedback")
    op.drop_index("idx_case_feedback_case_status_submitted", table_name="case_feedback")
    op.drop_table("case_feedback")
