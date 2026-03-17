"""Add case importance scoring schema.

Revision ID: 0008_case_importance_scoring
Revises: 0007_resilient_ingestion_cas
Create Date: 2026-03-17
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_case_importance_scoring"
down_revision = "0007_resilient_ingestion_cas"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    json_type = _json_type()

    # cases: importance fields
    op.add_column("cases", sa.Column("importance_score", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("importance_components", json_type, nullable=True))
    op.add_column("cases", sa.Column("importance_confidence", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("importance_override", json_type, nullable=True))
    op.create_index("ix_cases_importance_score", "cases", ["importance_score"])
    op.create_index("ix_cases_last_scored_at", "cases", ["last_scored_at"])

    # media mention table
    op.create_table(
        "case_media_mentions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credibility_score", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_case_media_case_published", "case_media_mentions", ["case_id", "published_at"])
    op.create_index("idx_case_media_credibility", "case_media_mentions", ["credibility_score"])

    # configurable scoring profile and audit logs
    op.create_table(
        "importance_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("weights_json", json_type, nullable=False),
        sa.Column("case_type_map_json", json_type, nullable=False),
        sa.Column("min_confidence", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("media_decay_lambda", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("monetary_cap", sa.Float(), nullable=False, server_default="50000000"),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_importance_configs_name"),
    )

    op.create_table(
        "importance_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("old_value", json_type, nullable=False),
        sa.Column("new_value", json_type, nullable=False),
        sa.Column("provenance", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_importance_audit_case_created", "importance_audit_logs", ["case_id", "created_at"])
    op.create_index("idx_importance_audit_action_created", "importance_audit_logs", ["action", "created_at"])

    # Seed default configuration
    seed_weights = {
        "w_politician": 0.30,
        "w_corruption": 0.20,
        "w_case_type": 0.15,
        "w_media": 0.15,
        "w_monetary": 0.10,
        "w_priority": 0.07,
        "w_historical": 0.03,
    }
    seed_case_map = {
        "criminal_corruption": 1.0,
        "pil": 0.9,
        "criminal": 0.7,
        "civil_land": 0.2,
        "tax": 0.4,
        "default": 0.3,
    }

    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO importance_configs
                    (name, weights_json, case_type_map_json, min_confidence, media_decay_lambda, monetary_cap)
                VALUES
                    (
                        :name,
                        CAST(:weights AS JSONB),
                        CAST(:case_map AS JSONB),
                        :min_conf,
                        :decay,
                        :cap
                    )
                """
            ).bindparams(
                name="default",
                weights=json.dumps(seed_weights),
                case_map=json.dumps(seed_case_map),
                min_conf=0.2,
                decay=0.05,
                cap=50000000,
            )
        )
    else:
        op.execute(
            sa.text(
                """
                INSERT INTO importance_configs
                    (name, weights_json, case_type_map_json, min_confidence, media_decay_lambda, monetary_cap)
                VALUES
                    (
                        :name,
                        :weights,
                        :case_map,
                        :min_conf,
                        :decay,
                        :cap
                    )
                """
            ).bindparams(
                name="default",
                weights=seed_weights,
                case_map=seed_case_map,
                min_conf=0.2,
                decay=0.05,
                cap=50000000,
            )
        )


def downgrade() -> None:
    op.drop_index("idx_importance_audit_action_created", table_name="importance_audit_logs")
    op.drop_index("idx_importance_audit_case_created", table_name="importance_audit_logs")
    op.drop_table("importance_audit_logs")

    op.drop_table("importance_configs")

    op.drop_index("idx_case_media_credibility", table_name="case_media_mentions")
    op.drop_index("idx_case_media_case_published", table_name="case_media_mentions")
    op.drop_table("case_media_mentions")

    op.drop_index("ix_cases_last_scored_at", table_name="cases")
    op.drop_index("ix_cases_importance_score", table_name="cases")
    op.drop_column("cases", "importance_override")
    op.drop_column("cases", "last_scored_at")
    op.drop_column("cases", "importance_confidence")
    op.drop_column("cases", "importance_components")
    op.drop_column("cases", "importance_score")
