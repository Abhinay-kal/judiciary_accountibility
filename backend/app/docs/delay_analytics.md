# Baseline-Adjusted Delay Analytics

## Objective

Compare each case duration to robust, context-aware baselines instead of absolute elapsed time.

## Baseline Levels

Fallback hierarchy:

1. `court_case_type`
2. `court`
3. `state_case_type`
4. `state`
5. `national_case_type`
6. `national`

## Robust Statistics

For each baseline bucket (`delay_baselines` table):

- median delay
- 75th percentile
- 90th percentile
- IQR
- sample size

## Delay Metrics on Cases

Persisted on `cases`:

- `normalized_delay`
- `delay_percentile`
- `robust_z_score`
- `delay_severity`
- `baseline_level_used`
- `baseline_sample_size`
- `baseline_confidence`
- `last_baseline_update`

## Confidence

Baseline confidence combines:

- sample size
- baseline recency
- spread stability (`IQR / median`)
- fallback depth penalty

## Batch Workflow

1. `app.tasks.delay_analytics.recompute_delay_baselines`
2. `app.tasks.delay_analytics.update_case_delay_analytics`

Scheduled daily in beat.

## Anomaly Rule

Case flagged as `baseline_delay_anomaly` when any is true:

- `normalized_delay >= 1.5`
- `delay_percentile >= 90`
- `robust_z_score >= 2`

## API

`GET /api/v1/cases` and `GET /api/v1/cases/{id}` include delay analytics fields and a display-ready summary sentence.

Supported filters:

- `min_normalized_delay`
- `delay_severity`
