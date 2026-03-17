# Open Data Export API

## Overview

The Open Data Export API provides reproducible, machine-readable datasets for the Court Case Delay & Justice Tracker — India.

Design goals:
- Transparency with safeguards
- Reproducible snapshots via dataset versioning
- Privacy-preserving exports
- Multi-format interoperability (CSV, JSON, Parquet, NDJSON)
- Scalable delivery (streaming, pre-generated files, compression)
- Abuse prevention (quotas, limits, throttling)

Base path:
- /api/v1/datasets

## Dataset Catalog

Datasets currently supported:
- case_metadata
- hearing_timelines
- court_statistics
- judge_metrics_aggregated
- delay_distributions
- flagged_cases
- external_coverage_links
- derived_analytics

Each catalog entry includes:
- dataset_id
- name
- description
- schema
- fields list
- update frequency
- version
- license
- data quality notes
- privacy classification
- methodology notes
- known limitations
- provenance summary
- permitted uses
- recommended citation

## Endpoints

### GET /datasets
Returns list of available datasets and summary metadata.

### GET /datasets/{id}
Returns full dataset metadata and documentation fields.

### GET /datasets/{id}/schema
Returns explicit schema, field definitions, and data dictionary.

### GET /datasets/{id}/v/{version}
Returns reproducible version descriptor for a dataset.

### GET /datasets/{id}/download
Exports dataset payload.

Query parameters:
- format: csv | json | parquet | ndjson
- version: optional (defaults to latest)
- state
- court
- case_type
- date_from
- date_to
- status
- importance_score
- max_rows
- compress: true|false
- stream: true|false (NDJSON streaming)
- precomputed: true|false (cached file reuse)
- cloud_link: true|false (returns cloud-style link response)

### GET /datasets/monitoring/usage
Returns download counters, error counters, popular datasets, cache stats.
Requires API key tier.

## Filtering

Supported filters:
- state
- court
- case_type
- date range (date_from/date_to)
- status
- importance score (minimum)

Filtering is applied to source queries before export generation.

## Formats

Supported output formats:
- CSV
- JSON
- Parquet
- NDJSON

Notes:
- Parquet requires pandas + parquet engine
- NDJSON supports chunked streaming for large exports
- Any format can be compressed with gzip via compress=true

## Versioning

Versioned access path:
- /datasets/{dataset_id}/v/{version}

Version registry behavior:
- resolves explicit versions
- defaults to latest when version omitted
- retains historical versions for reproducibility workflows

## Privacy and Anonymization

Anonymization pipeline is applied before serialization:
- Masks sensitive keys such as address, contact, email, phone, identifiers
- Redacts direct PII-like patterns in text (email/phone/id patterns)
- Removes sensitive free-text fields from selected datasets

Sensitive personal data is excluded from exports.

## Delivery and Performance

Delivery mechanisms:
- Direct download response
- Streaming NDJSON response for large payloads
- Pre-generated/cached file serving from disk
- Cloud-style link responses for asynchronous delivery patterns

Performance optimizations:
- Precomputed export cache
- Chunked NDJSON generation
- Optional compression
- max_rows safeguards to control export size

## Access Control and Abuse Prevention

Access tiers:
- Public tier: lower quotas and row limits
- API key tier: higher quotas and row limits

Abuse controls:
- Hourly request quotas per client+tier
- max_rows enforcement
- endpoint-level throttling for export paths

API key source:
- OPEN_DATA_API_KEYS env var (comma-separated)

## Data Quality Indicators

Each export metadata payload includes indicators:
- completeness
- coverage
- confidence_level
- missing_data_rate

Also includes:
- record_count
- masked_fields
- filters_applied
- last_updated timestamp

## Citation

Recommended citation included in catalog metadata:
- "Data from Court Case Delay & Justice Tracker, retrieved on [date]."

## License

Open data license used in catalog:
- Open Data Commons Attribution License (ODC-By 1.0)

Permitted uses are provided per dataset entry.

## UI Integration

Frontend catalog page:
- /open-data

Features:
- Dataset listing
- Download buttons
- Filter interface
- Direct schema/documentation links
- Citation visibility

## Tests

Test file:
- backend/tests/test_open_data_api.py

Coverage includes:
- dataset catalog availability
- filtering correctness
- format validity (CSV/JSON/NDJSON)
- version consistency
- anonymization behavior
- large NDJSON streaming behavior
- API endpoint behavior and limits

## Operational Notes

Monitoring counters currently tracked in-memory:
- download counts
- error counts
- bytes served
- popular datasets ranking
- cache item count

For production hardening, counters can be exported to Prometheus and quotas moved to Redis for multi-instance consistency.
