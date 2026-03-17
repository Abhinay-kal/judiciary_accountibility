# Dormancy Detector (Silent Case Death Detector)

## Purpose

Identify pending cases with prolonged, abnormal inactivity relative to contextual hearing-gap baselines, while applying defamation-safe safeguards and explicit exclusion conditions.

## Package

- `backend/app/analytics/dormancy/features.py`
- `backend/app/analytics/dormancy/baseline.py`
- `backend/app/analytics/dormancy/rules.py`
- `backend/app/analytics/dormancy/scoring.py`
- `backend/app/analytics/dormancy/explanations.py`

## Detection Logic

A case is considered a dormancy candidate when all are true:

1. Pending and not disposed
2. No near-term future listing
3. Relative inactivity exceeds normalized threshold
4. Absolute inactivity exceeds configured minimum days

### Relative inactivity

`normalized_inactivity = days_since_last_hearing / contextual_median_gap`

Context hierarchy for baselines:

1. court + case_type + stage
2. court + case_type
3. court
4. state + case_type
5. state
6. national + case_type
7. national

## Exclusions

Do not flag when:

- disposed or not pending
- active stay order
- future hearing scheduled soon
- recent transfer detected
- low data confidence / insufficient baseline evidence

## Severity and Score

Severities:

- `mild_dormancy`
- `significant_dormancy`
- `severe_dormancy`
- `extreme_inactivity`

`dormancy_score` is in `[0, 1]` and combines:

- normalized inactivity
- absolute inactivity
- case importance
- worsening pattern indicators (increasing gaps, repeated adjournments)

## Reactivation Handling

Dormancy is downgraded when new activity appears (listing/order/hearing) or exclusions now apply. Existing dormant flags are deactivated.

## Database Fields

Added to `cases` table:

- `dormancy_status`
- `dormancy_score`
- `days_since_last_activity`
- `last_activity_date`
- `dormancy_last_updated`

Migration: `backend/alembic/versions/0018_dormancy_case_fields.py`

## API Endpoints

- `GET /api/v1/cases/{id}/dormancy`
- `GET /api/v1/cases/dormant`

`/cases/dormant` supports severity and score filtering.

## Timeline Marker

Dormancy response includes a timeline marker message:

- `Case entered dormant state on YYYY-MM-DD`

## Batch Processing

Daily task:

- Celery task: `app.tasks.dormancy_analytics.recompute_case_dormancy`
- Scheduler slot: `daily-dormancy-recompute`

## Defamation Safety

Outputs are framed as inactivity analytics signals only and explicitly avoid misconduct allegations.
