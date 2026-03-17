"""Add field-level provenance tables.

Revision ID: 0016_field_level_provenance
Revises: 0015_persuasion_impact_fields
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_field_level_provenance"
down_revision = "0015_persuasion_impact_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_provenance",
        sa.Column("provenance_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("field_value_hash", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_payload_ref", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=120), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("fetch_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_run_id", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("transformation_steps", sa.JSON(), nullable=False),
        sa.Column("is_primary_source", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("provenance_id"),
    )
    op.create_index("idx_field_provenance_entity_field", "field_provenance", ["entity_type", "entity_id", "field_name", "created_at"])
    op.create_index("idx_field_provenance_hash", "field_provenance", ["field_value_hash"])
    op.create_index("idx_field_provenance_source", "field_provenance", ["source_name", "fetch_time"])
    op.create_index("idx_field_provenance_run", "field_provenance", ["ingestion_run_id"])
    op.create_index("idx_field_provenance_primary", "field_provenance", ["entity_type", "entity_id", "field_name", "is_primary_source"])

    op.create_table(
        "provenance_links",
        sa.Column("link_id", sa.Integer(), nullable=False),
        sa.Column("parent_provenance_id", sa.Integer(), nullable=False),
        sa.Column("child_provenance_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_provenance_id"], ["field_provenance.provenance_id"]),
        sa.ForeignKeyConstraint(["child_provenance_id"], ["field_provenance.provenance_id"]),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint("parent_provenance_id", "child_provenance_id", "relationship_type", name="uq_provenance_links_rel"),
    )
    op.create_index("idx_provenance_links_parent", "provenance_links", ["parent_provenance_id"])
    op.create_index("idx_provenance_links_child", "provenance_links", ["child_provenance_id"])
    op.create_index("idx_provenance_links_rel", "provenance_links", ["relationship_type"])


def downgrade() -> None:
    op.drop_index("idx_provenance_links_rel", table_name="provenance_links")
    op.drop_index("idx_provenance_links_child", table_name="provenance_links")
    op.drop_index("idx_provenance_links_parent", table_name="provenance_links")
    op.drop_table("provenance_links")

    op.drop_index("idx_field_provenance_primary", table_name="field_provenance")
    op.drop_index("idx_field_provenance_run", table_name="field_provenance")
    op.drop_index("idx_field_provenance_source", table_name="field_provenance")
    op.drop_index("idx_field_provenance_hash", table_name="field_provenance")
    op.drop_index("idx_field_provenance_entity_field", table_name="field_provenance")
    op.drop_table("field_provenance")
