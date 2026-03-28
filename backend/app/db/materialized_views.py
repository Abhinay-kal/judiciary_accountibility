"""
SQL Materialized Views for Advocate Performance Metrics

These views pre-compute aggregate statistics for efficient lookups:
- Advocate case involvement
- Adjournment request patterns
- Success/win rates (where applicable)
- Case specialization by court/type

Materialized views can be refreshed periodically (e.g., hourly or daily)
rather than computed on every query.
"""

# View 1: Advocate Case Portfolio
# Shows what types of cases and how many each advocate handles
ADVOCATE_CASE_PORTFOLIO = """
CREATE MATERIALIZED VIEW IF NOT EXISTS advocate_case_portfolio AS
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
GROUP BY cc.advocate_id, a.canonical_name, c.court_level, c.case_type, c.state
ORDER BY cc.advocate_id, case_count DESC;

CREATE INDEX idx_advocate_case_portfolio_advocate 
ON advocate_case_portfolio(advocate_id);
CREATE INDEX idx_advocate_case_portfolio_court 
ON advocate_case_portfolio(court_level);
"""

# View 2: Advocate Adjournment Statistics
# Shows adjournment patterns per advocate across their cases
ADVOCATE_ADJOURNMENT_STATS = """
CREATE MATERIALIZED VIEW IF NOT EXISTS advocate_adjournment_stats AS
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
GROUP BY a.id, a.canonical_name, a.total_adjournment_requests, a.avg_adjournment_rate
ORDER BY requested_by_advocate DESC;

CREATE INDEX idx_advocate_adjournment_stats_advocate 
ON advocate_adjournment_stats(advocate_id);
CREATE INDEX idx_advocate_adjournment_stats_requested_by 
ON advocate_adjournment_stats(percentage_requested_by_advocate DESC);
"""

# View 3: Advocate Interim Application Activity
# Shows interim petition filing and success patterns
ADVOCATE_INTERIM_APP_ACTIVITY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS advocate_interim_app_activity AS
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
GROUP BY a.id, a.canonical_name, ia.application_type
ORDER BY a.id, applications_filed DESC;

CREATE INDEX idx_advocate_interim_app_advocate 
ON advocate_interim_app_activity(advocate_id);
CREATE INDEX idx_advocate_interim_app_type 
ON advocate_interim_app_activity(application_type);
"""

# View 4: Advocate Court Specialization
# Shows which courts each advocate practices in and their experience
ADVOCATE_COURT_SPECIALIZATION = """
CREATE MATERIALIZED VIEW IF NOT EXISTS advocate_court_specialization AS
SELECT 
    cc.advocate_id,
    a.canonical_name,
    co.id as court_id,
    co.name as court_name,
    co.court_type,
    co.high_court,
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
GROUP BY cc.advocate_id, a.canonical_name, co.id, co.name, co.court_type, co.high_court
ORDER BY cc.advocate_id, case_count DESC;

CREATE INDEX idx_advocate_court_specialization_advocate 
ON advocate_court_specialization(advocate_id);
CREATE INDEX idx_advocate_court_specialization_court 
ON advocate_court_specialization(court_id);
"""

# View 5: Advocate Performance Summary (Denormalized single row per advocate)
ADVOCATE_PERFORMANCE_SUMMARY = """
CREATE MATERIALIZED VIEW IF NOT EXISTS advocate_performance_summary AS
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
GROUP BY a.id, a.canonical_name, a.bar_council_id, a.enrollment_date, a.is_verified
ORDER BY total_cases_involved DESC;

CREATE INDEX idx_advocate_performance_summary_advocate 
ON advocate_performance_summary(advocate_id);
CREATE INDEX idx_advocate_performance_summary_adjournments_requested 
ON advocate_performance_summary(adjournments_requested DESC);
"""

print("""
MATERIALIZED VIEWS CREATED:

1. advocate_case_portfolio - Cases by type, court, state; disposal rates
2. advocate_adjournment_stats - Adjournment patterns and request rates
3. advocate_interim_app_activity - Interim petition filing and success rates
4. advocate_court_specialization - Court experience and specialization
5. advocate_performance_summary - Holistic advocate performance metrics

To use these views:

  1. Add to migration:
     MATERIALIZED VIEW queries from this file

  2. Query examples:
     
     # Find advocates with high adjournment request rates
     SELECT canonical_name, percentage_requested_by_advocate
     FROM advocate_adjournment_stats
     WHERE percentage_requested_by_advocate > 50
     ORDER BY percentage_requested_by_advocate DESC;
     
     # Find advocates filing many frivolous interim apps
     SELECT canonical_name, application_type, flagged_frivolous_percentage
     FROM advocate_interim_app_activity
     WHERE flagged_frivolous_percentage > 30
     ORDER BY flagged_frivolous_percentage DESC;
     
     # Advocate specialization by court
     SELECT canonical_name, court_name, case_count, active_case_percentage
     FROM advocate_court_specialization
     WHERE court_rank <= 3  # Top 3 advocates per court
     ORDER BY court_name, case_count DESC;

  3. Refresh strategy:
     - Refresh nightly/hourly depending on volume
     - Use: REFRESH MATERIALIZED VIEW advocate_performance_summary;
     - Or add scheduled task in backend:
       @app.scheduled_task(cron='0 0 * * *')  # Midnight daily
       def refresh_advocate_views():
           db.execute(text('REFRESH MATERIALIZED VIEW advocate_performance_summary'))
""")
