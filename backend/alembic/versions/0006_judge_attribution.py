"""Add judge registry and per-hearing assignments.

Revision ID: 0006_judge_attribution
Revises: 0005_hearing_outcomes
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_judge_attribution"
down_revision = "0005_hearing_outcomes"
branch_labels = None
depends_on = None


JUDGE_ASSIGNMENT_ROLE_VALUES = (
    "PRESIDING",
    "CO_JUDGE",
    "JUDGE_MEMBER",
    "AMICUS",
    "OTHER",
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                "DO $$ BEGIN "
                "CREATE TYPE judge_assignment_role AS ENUM ('PRESIDING','CO_JUDGE','JUDGE_MEMBER','AMICUS','OTHER'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "END $$;"
            )
        )
        role_type = postgresql.ENUM(
            *JUDGE_ASSIGNMENT_ROLE_VALUES,
            name="judge_assignment_role",
            create_type=False,
        )
        json_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        role_type = sa.String(length=20)
        json_type = sa.JSON()

    op.add_column("hearings", sa.Column("raw_bench", sa.Text(), nullable=True))

    op.create_table(
        "judge_registry",
        sa.Column("judge_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("name_variants", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("phonetic_keys", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("service_number", sa.String(length=100), nullable=True),
        sa.Column("court_id", sa.Integer(), sa.ForeignKey("courts.id"), nullable=True),
        sa.Column("known_designations", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("judge_id"),
    )
    op.create_index("idx_judge_registry_canonical_name", "judge_registry", ["canonical_name"])

    if dialect == "postgresql":
        op.create_index(
            "idx_judge_registry_name_variants_gin",
            "judge_registry",
            ["name_variants"],
            postgresql_using="gin",
        )

    op.create_table(
        "judge_assignments",
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("hearing_id", sa.Integer(), sa.ForeignKey("hearings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_id", sa.String(length=36), sa.ForeignKey("judge_registry.judge_id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_name_raw", sa.Text(), nullable=False),
        sa.Column("role", role_type, nullable=False),
        sa.Column("is_presiding", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sequence_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attribution_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matched_on", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("ingestion_sources.id"), nullable=True),
        sa.Column("ingestion_run_id", sa.String(length=64), nullable=True),
        sa.Column("raw_bench_snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=True),
        sa.Column("annotated_by", sa.Integer(), nullable=True),
        sa.Column("annotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("hearing_id", "judge_id", "sequence_index", name="uq_hearing_judge_sequence"),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index("idx_judge_assignments_hearing", "judge_assignments", ["hearing_id"])
    op.create_index("idx_judge_assignments_judge", "judge_assignments", ["judge_id"])
    op.create_index("idx_judge_assignments_confidence", "judge_assignments", ["attribution_confidence"])

    op.create_table(
        "judge_attribution_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("hearing_id", sa.Integer(), sa.ForeignKey("hearings.id"), nullable=True),
        sa.Column("assignment_id", sa.String(length=36), sa.ForeignKey("judge_assignments.assignment_id"), nullable=True),
        sa.Column("judge_registry_id", sa.String(length=36), sa.ForeignKey("judge_registry.judge_id"), nullable=True),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("old_value", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("new_value", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if dialect == "postgresql" else None),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_judge_attribution_audit_hearing", "judge_attribution_audits", ["hearing_id", "created_at"])
    op.create_index("idx_judge_attribution_audit_registry", "judge_attribution_audits", ["judge_registry_id", "created_at"])

    # Low-risk backfill from existing judges + hearings.judge_id linkage.
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO judge_registry (
                    judge_id,
                    canonical_name,
                    name_variants,
                    phonetic_keys,
                    service_number,
                    court_id,
                    known_designations,
                    first_seen,
                    last_seen,
                    metadata,
                    is_provisional,
                    created_at,
                    updated_at
                )
                SELECT
                    md5('legacy-judge-' || j.id::text),
                    lower(regexp_replace(j.name, '[^a-zA-Z0-9 ]', ' ', 'g')),
                    jsonb_build_object('variants', jsonb_build_array(j.name)),
                    jsonb_build_object('keys', jsonb_build_array()),
                    NULL,
                    j.court_id,
                    jsonb_build_object('values', jsonb_build_array()),
                    now(),
                    now(),
                    jsonb_build_object('backfill', true, 'legacy_judge_id', j.id),
                    true,
                    now(),
                    now()
                FROM judges j
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM judge_registry r
                    WHERE r.metadata->>'legacy_judge_id' = j.id::text
                )
                """
            )
        )

        op.execute(
            sa.text(
                """
                INSERT INTO judge_assignments (
                    assignment_id,
                    hearing_id,
                    judge_id,
                    judge_name_raw,
                    role,
                    is_presiding,
                    sequence_index,
                    attribution_confidence,
                    matched_on,
                    source_id,
                    ingestion_run_id,
                    raw_bench_snapshot_id,
                    parser_version,
                    annotated_by,
                    annotated_at,
                    metadata_json,
                    created_at,
                    updated_at
                )
                SELECT
                    md5('legacy-assignment-' || h.id::text || '-' || h.judge_id::text),
                    h.id,
                    md5('legacy-judge-' || h.judge_id::text),
                    COALESCE(j.name, ''),
                    'PRESIDING',
                    true,
                    0,
                    0.55,
                    'legacy',
                    NULL,
                    NULL,
                    NULL,
                    'judge-backfill-v1',
                    NULL,
                    NULL,
                    jsonb_build_object('legacy_backfill', true),
                    now(),
                    now()
                FROM hearings h
                JOIN judges j ON j.id = h.judge_id
                WHERE h.judge_id IS NOT NULL
                  AND NOT EXISTS (
                        SELECT 1
                        FROM judge_assignments a
                        WHERE a.hearing_id = h.id
                          AND a.judge_id = md5('legacy-judge-' || h.judge_id::text)
                          AND a.sequence_index = 0
                    )
                """
            )
        )


def downgrade() -> None:
    op.drop_index("idx_judge_attribution_audit_registry", table_name="judge_attribution_audits")
    op.drop_index("idx_judge_attribution_audit_hearing", table_name="judge_attribution_audits")
    op.drop_table("judge_attribution_audits")

    op.drop_index("idx_judge_assignments_confidence", table_name="judge_assignments")
    op.drop_index("idx_judge_assignments_judge", table_name="judge_assignments")
    op.drop_index("idx_judge_assignments_hearing", table_name="judge_assignments")
    op.drop_table("judge_assignments")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("idx_judge_registry_name_variants_gin", table_name="judge_registry")

    op.drop_index("idx_judge_registry_canonical_name", table_name="judge_registry")
    op.drop_table("judge_registry")

    op.drop_column("hearings", "raw_bench")

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS judge_assignment_role"))
