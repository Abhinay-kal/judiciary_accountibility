"""Create advocate performance materialized views.

Revision ID: 0022_advocate_materialized_views
Revises: 0021_advocate_entity_model
Create Date: 2026-03-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_advocate_materialized_views"
down_revision = "0021_advocate_entity_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # View 1: Advocate Case Portfolio
    op.execute("""
    CREATE MATERIALIZED VIEW advocate_case_portfolio AS
    SELECT 
        cc.advocate_id,
        a.canonical_name,
        c.court_level,
        c.case_type,
        c.state,
        COUNT(DISTINCT cc.case_id) as case_count,
        AVG(CAST(EXTRACT(EPOCH FROM (c.updated_at - c.filing_date)) AS INTEGER) / 86400.0) as avg_case_duration_days,
        COUNT(DISTINCT CASE WHEN c.is_disposed = true THEN c.id END) as disposed_count,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN c.is_disposed = true THEN c.id END) 
            / NULLIF(COUNT(DISTINCT c.id), 0), 1) as disposal_percentage
    FROM case_counsel cc
    JOIN advocates a ON cc.advocate_id = a.id
    JOIN cases c ON cc.case_id = c.id
    WHERE cc.deleted_at IS NULL
      AND a.deleted_at IS NULL
      AND c.deleted_at IS NULL
    GROUP BY cc.advocate_id, a.canonical_name, c.court_level, c.case_type, c.state;
    """)
    
    op.execute("""
    CREATE INDEX idx_advocate_case_portfolio_advocate 
    ON advocate_case_portfolio(advocate_id)
    """)
    
    # View 2: Advocate Adjournment Statistics
    op.execute("""
    CREATE MATERIALIZED VIEW advocate_adjournment_stats AS
    SELECT 
        a.id as advocate_id,
        a.canonical_name,
        COUNT(DISTINCT adj.case_id) as cases_with_adjournments,
        COUNT(DISTINCT adj.id) as total_adjournment_events,
        COUNT(DISTINCT CASE WHEN adj.requested_by = a.id THEN adj.id END) as requested_by_advocate,
        COUNT(DISTINCT CASE WHEN adj.reason_type = 'on_request' THEN adj.id END) as on_request_count,
        COUNT(DISTINCT CASE WHEN adj.was_contested = true THEN adj.id END) as contested_count,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN adj.requested_by = a.id THEN adj.id END)
            / NULLIF(COUNT(DISTINCT adj.id), 0), 1) as percentage_requested_by_advocate,
        a.total_adjournment_requests,
        a.avg_adjournment_rate,
        COUNT(DISTINCT c.id) as total_cases_involved
    FROM advocates a
    LEFT JOIN case_counsel cc ON a.id = cc.advocate_id AND cc.deleted_at IS NULL
    LEFT JOIN adjournments adj ON (
        (adj.requested_by = a.id OR cc.case_id = adj.case_id)
        AND adj.deleted_at IS NULL
    )
    LEFT JOIN cases c ON cc.case_id = c.id AND c.deleted_at IS NULL
    WHERE a.deleted_at IS NULL
    GROUP BY a.id, a.canonical_name, a.total_adjournment_requests, a.avg_adjournment_rate;
    """)
    
    op.execute("""
    CREATE INDEX idx_advocate_adjournment_stats_advocate 
    ON advocate_adjournment_stats(advocate_id)
    """)
    
    # View 3: Advocate Interim Application Activity
    op.execute("""
    CREATE MATERIALIZED VIEW advocate_interim_app_activity AS
    SELECT 
        a.id as advocate_id,
        a.canonical_name,
        ia.application_type,
        COUNT(DISTINCT ia.id) as applications_filed,
        COUNT(DISTINCT CASE WHEN ia.decision_status = 'GRANTED' THEN ia.id END) as granted_count,
        COUNT(DISTINCT CASE WHEN ia.decision_status = 'REJECTED' THEN ia.id END) as rejected_count,
        COUNT(DISTINCT CASE WHEN ia.decision_status = 'DISMISSED' THEN ia.id END) as dismissed_count,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN ia.decision_status = 'GRANTED' THEN ia.id END)
            / NULLIF(COUNT(DISTINCT ia.id), 0), 1) as grant_percentage,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN ia.is_frivolous_indicator = true THEN ia.id END)
            / NULLIF(COUNT(DISTINCT ia.id), 0), 1) as flagged_frivolous_percentage,
        ROUND(AVG(COALESCE(ia.delay_caused_days, 0)), 1) as avg_delay_caused_days,
        SUM(COALESCE(ia.delay_caused_days, 0)) as total_delay_caused_days
    FROM advocates a
    LEFT JOIN interim_applications ia ON a.id = ia.applicant_advocate_id AND ia.deleted_at IS NULL
    WHERE a.deleted_at IS NULL
      AND ia.application_type IS NOT NULL
    GROUP BY a.id, a.canonical_name, ia.application_type;
    """)
    
    op.execute("""
    CREATE INDEX idx_advocate_interim_app_advocate 
    ON advocate_interim_app_activity(advocate_id)
    """)
    
    # View 4: Advocate Court Specialization
    op.execute("""
    CREATE MATERIALIZED VIEW advocate_court_specialization AS
    SELECT 
        cc.advocate_id,
        a.canonical_name,
        co.id as court_id,
        co.name as court_name,
        co.level as court_level,
        COUNT(DISTINCT cc.case_id) as case_count,
        COUNT(DISTINCT CASE WHEN cc.role = 'PETITIONER' THEN cc.case_id END) as petitioner_cases,
        COUNT(DISTINCT CASE WHEN cc.role = 'RESPONDENT' THEN cc.case_id END) as respondent_cases,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN cc.is_currently_appearing = true THEN cc.case_id END)
            / NULLIF(COUNT(DISTINCT cc.case_id), 0), 1) as active_case_percentage,
        RANK() OVER (PARTITION BY co.id ORDER BY COUNT(DISTINCT cc.case_id) DESC) as court_rank
    FROM case_counsel cc
    JOIN advocates a ON cc.advocate_id = a.id
    JOIN cases c ON cc.case_id = c.id
    JOIN courts co ON c.court_id = co.id
    WHERE cc.deleted_at IS NULL
      AND a.deleted_at IS NULL
      AND c.deleted_at IS NULL
    GROUP BY cc.advocate_id, a.canonical_name, co.id, co.name, co.level;
    """)
    
    op.execute("""
    CREATE INDEX idx_advocate_court_specialization_advocate 
    ON advocate_court_specialization(advocate_id)
    """)
    
    # View 5: Advocate Performance Summary
    op.execute("""
    CREATE MATERIALIZED VIEW advocate_performance_summary AS
    SELECT 
        a.id as advocate_id,
        a.canonical_name,
        a.bar_council_id,
        a.enrollment_date,
        a.is_verified,
        COUNT(DISTINCT c.id) as total_cases_involved,
        COUNT(DISTINCT CASE WHEN cc.is_currently_appearing = true THEN c.id END) as active_cases,
        COUNT(DISTINCT CASE WHEN c.is_disposed = true THEN c.id END) as disposed_cases,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN c.is_disposed = true THEN c.id END)
            / NULLIF(COUNT(DISTINCT c.id), 0), 1) as case_disposal_rate,
        COUNT(DISTINCT adj.id) as total_adjournments_in_cases,
        COUNT(DISTINCT CASE WHEN adj.requested_by = a.id THEN adj.id END) as adjournments_requested,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN adj.requested_by = a.id THEN adj.id END)
            / NULLIF(COUNT(DISTINCT adj.id), 0), 1) as pct_requested_by_advocate,
        COUNT(DISTINCT ia.id) as interim_apps_filed,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN ia.decision_status = 'GRANTED' THEN ia.id END)
            / NULLIF(COUNT(DISTINCT ia.id), 0), 1) as interim_grant_rate,
        COUNT(DISTINCT co.id) as courts_practicing_in,
        COUNT(DISTINCT c.case_type) as case_types_handled,
        AVG(CAST(EXTRACT(EPOCH FROM (c.updated_at - c.filing_date)) AS INTEGER) / 86400.0) as avg_case_duration_days,
        CURRENT_TIMESTAMP as computed_at
    FROM advocates a
    LEFT JOIN case_counsel cc ON a.id = cc.advocate_id AND cc.deleted_at IS NULL
    LEFT JOIN cases c ON cc.case_id = c.id AND c.deleted_at IS NULL
    LEFT JOIN adjournments adj ON c.id = adj.case_id AND adj.deleted_at IS NULL
    LEFT JOIN interim_applications ia ON ia.applicant_advocate_id = a.id AND ia.deleted_at IS NULL
    LEFT JOIN courts co ON c.court_id = co.id
    WHERE a.deleted_at IS NULL
    GROUP BY a.id, a.canonical_name, a.bar_council_id, a.enrollment_date, a.is_verified;
    """)
    
    op.execute("""
    CREATE INDEX idx_advocate_performance_summary_advocate 
    ON advocate_performance_summary(advocate_id)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS advocate_performance_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS advocate_court_specialization CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS advocate_interim_app_activity CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS advocate_adjournment_stats CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS advocate_case_portfolio CASCADE")
