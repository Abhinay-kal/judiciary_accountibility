"""Add CAS raw payloads table and ingestion provenance columns.

Revision ID: 0007_resilient_ingestion_cas
Revises: 0006_judge_attribution
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_resilient_ingestion_cas"
down_revision = "0006_judge_attribution"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()

    op.add_column("ingestion_runs", sa.Column("raw_payload_checksum", sa.String(length=64), nullable=True))
    op.add_column("ingestion_runs", sa.Column("raw_object_ref", sa.Text(), nullable=True))
    op.add_column("ingestion_runs", sa.Column("parser_version", sa.String(length=64), nullable=True))
    op.add_column("ingestion_runs", sa.Column("provenance_json", json_type, nullable=True))
    op.create_index("ix_ingestion_runs_raw_payload_checksum", "ingestion_runs", ["raw_payload_checksum"])

    op.create_table(
        "raw_payloads",
        sa.Column("payload_id", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_ref", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
        sa.Column("provenance_json", json_type, nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["ingestion_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("payload_id"),
        sa.UniqueConstraint("checksum", name="uq_raw_payloads_checksum"),
    )
    op.create_index("idx_raw_payloads_source_retrieved", "raw_payloads", ["source_id", "retrieved_at"])
    op.create_index("idx_raw_payloads_ingestion_run", "raw_payloads", ["ingestion_run_id"])

    op.execute("UPDATE ingestion_runs SET provenance_json = '{}' WHERE provenance_json IS NULL")
    op.execute("UPDATE raw_payloads SET provenance_json = '{}' WHERE provenance_json IS NULL")

    op.alter_column("ingestion_runs", "provenance_json", nullable=False)
    op.alter_column("raw_payloads", "provenance_json", nullable=False)


def downgrade() -> None:
    op.drop_index("idx_raw_payloads_ingestion_run", table_name="raw_payloads")
    op.drop_index("idx_raw_payloads_source_retrieved", table_name="raw_payloads")
    op.drop_table("raw_payloads")

    op.drop_index("ix_ingestion_runs_raw_payload_checksum", table_name="ingestion_runs")
    op.drop_column("ingestion_runs", "provenance_json")
    op.drop_column("ingestion_runs", "parser_version")
    op.drop_column("ingestion_runs", "raw_object_ref")
    op.drop_column("ingestion_runs", "raw_payload_checksum")
