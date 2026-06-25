"""Enable pg_trgm and add trigram GIN index for judge registry name matching.

Revision ID: 0023_judge_registry_name_trgm_gin
Revises: 0022_advocate_materialized_views
Create Date: 2026-05-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0023_judge_registry_name_trgm_gin"
down_revision = "0022_advocate_materialized_views"
branch_labels = None
depends_on = None


INDEX_NAME = "idx_judge_registry_name_trgm_gin"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("judge_registry")}
    if INDEX_NAME in existing_indexes:
        return

    metadata = sa.MetaData()
    judge_registry = sa.Table(
        "judge_registry",
        metadata,
        sa.Column("canonical_name", sa.String(length=255), key="name"),
    )

    sa.Index(
        INDEX_NAME,
        judge_registry.c.name,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    ).create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("judge_registry")}
    if INDEX_NAME in existing_indexes:
        op.drop_index(INDEX_NAME, table_name="judge_registry")