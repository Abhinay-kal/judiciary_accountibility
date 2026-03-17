# Survival Analysis

This module provides right-censored time-to-disposal analytics for court cases using Kaplan-Meier estimators and precomputed cohort curves.

## Scope

- Estimates pending probability over case age for specific cohorts.
- Supports stratification by `court`, `state`, `judge`, and `national` pools.
- Computes confidence intervals using Greenwood variance.
- Produces smoothed hazard rates for operational monitoring.
- Powers case-level survival prediction and anomaly flags.

## Data Model

### Case fields

- `case_duration_days`: Duration in days from filing to disposal or censoring date.
- `is_disposed`: Boolean event indicator (`true` for disposed, `false` for right-censored).

### Precomputed table: `survival_curves`

Each row represents one cohort curve keyed by:

- `grouping_type`
- `grouping_value`
- `case_type` (nullable)

Stored arrays:

- `time_points`
- `survival_probabilities`
- `lower_ci`
- `upper_ci`
- `hazard_rates`

Metadata:

- `median_time`
- `sample_size`
- `event_count`
- `computed_at`

## Batch Processing

Celery task pipeline:

- `recompute_survival_curves`: refreshes case-level duration/event and recomputes cohort curves.
- `flag_survival_anomalies`: marks extremely delayed pending cases using percentile thresholds.
- `run_survival_pipeline`: convenience wrapper for both steps.

Default schedule:

- Daily recomputation of curves.
- Daily anomaly flagging.

## API

### `GET /api/v1/survival/curve`

Query parameters:

- `grouping_type` (required)
- `grouping_value` (required)
- `case_type` (optional)

Returns:

- curve arrays (time/survival/CI/hazard)
- one-, two-, five-, and ten-year survival snapshots
- cumulative incidence at ten years
- median and sample metadata

### `GET /api/v1/cases/{case_id}/survival`

Returns case-specific prediction based on the best available cohort fallback order:

1. `court_case_type`
2. `court`
3. `state_case_type`
4. `state`
5. `national` with case type
6. `national` overall

Response includes:

- current case age
- selected comparison cohort
- survival at current age
- survival after configured forecast horizon
- percentile rank
- unusual delay flag
- summary sentence

## Configuration

Environment variables:

- `SURVIVAL_WINDOW_YEARS`
- `SURVIVAL_MIN_SAMPLE_SIZE`
- `SURVIVAL_RECOMPUTE_BATCH_SIZE`
- `SURVIVAL_PREDICTION_HORIZON_DAYS`
- `SURVIVAL_UNUSUAL_PERCENTILE_THRESHOLD`
- `SURVIVAL_LOW_PROBABILITY_THRESHOLD`

## Statistical Notes

- Right-censoring is applied for pending cases at observation time.
- Tied event/censor times are handled at each unique time bucket.
- Confidence intervals use Greenwood variance approximation with normal quantiles.
- Curves with insufficient sample size are skipped to avoid unstable estimates.
