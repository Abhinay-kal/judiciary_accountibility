# Field-Level Data Provenance

## Purpose
This module provides immutable, field-level lineage for case-tracker data so each value can be traced to source, extraction, and transformation details.

## Data Model
### field_provenance
Stores one append-only provenance record per observed field value.

Key columns:
- provenance_id
- entity_type
- entity_id
- field_name
- field_value_hash
- source_name
- source_type
- source_url
- raw_payload_ref
- extraction_method
- parser_version
- fetch_time
- ingestion_run_id
- confidence_score
- transformation_steps
- is_primary_source
- created_at

### provenance_links
Stores explicit lineage and conflict links.

Relationship types:
- DERIVED_FROM
- CONFLICTS_WITH
- CONFIRMED_BY

## Design Guarantees
- Original source context is retained per record.
- Multiple sources are supported for the same field.
- Records are append-only; no overwrite path is used.
- Hashing protects value identity checks.
- Derived fields can point to all parent provenance entries.
- Conflicts are visible through linkage and query APIs.

## API Endpoints
- GET /cases/{id}/provenance
- GET /provenance/field?entity_type=...&entity_id=...&field_name=...
- GET /provenance/source/{source_id}

## Reconstruction
`reconstruct_entity_state(...)` rebuilds best-known entity state by selecting the strongest record per field using:
1. `is_primary_source`
2. confidence score
3. recency

## Performance Notes
- Compound index on `(entity_type, entity_id, field_name, created_at)` supports high-volume field lookups.
- Source/run indexes support audit and incident investigation queries.
- `primary` index supports quick best-record retrieval.

## UI Usage
The case page can call `/cases/{id}/provenance` and show source tooltip text for key fields.

Example tooltip text:
"Filing date from High Court cause list, retrieved on 2024-06-01"
