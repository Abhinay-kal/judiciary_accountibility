# Shareable Investigation Pages

## Overview
Investigation pages provide permanent, citation-ready records for flagged cases.

Permanent URL patterns:
- /investigation/{case_id}
- /investigation/{case_id}/v/{version_number}

## Content sections
Each generated investigation page includes:
1. Case summary
2. Timeline of events
3. Key metrics panel
4. Detected anomalies/patterns
5. Evidence sources
6. Methodology explanation
7. Confidence indicators
8. Right-to-respond section
9. Last updated timestamp
10. Version history context

## Snapshot model
Table: investigation_snapshots
- snapshot_id (PK)
- case_id
- version_number
- content_hash
- generated_at
- data_cutoff_date
- snapshot_data (JSON)
- is_current

Snapshots are immutable. If new content hash is unchanged, the latest snapshot is reused.

## API endpoints
- GET /api/v1/investigation/{case_id}
- GET /api/v1/investigation/{case_id}/v/{version_number}
- GET /api/v1/investigation/{case_id}/versions
- GET /api/v1/investigation/{case_id}/export/pdf
- GET /api/v1/investigation/{case_id}/export/json
- GET /api/v1/investigation/{case_id}/export/archive
- GET /api/v1/investigation/search

## Export options
- PDF: lightweight generated PDF with summary, metrics, timestamps, and disclaimer.
- Printable HTML: rendering used for web and print-friendly views.
- JSON package: report payload plus snapshot metadata.
- Offline archive: zip with report.html, report.json, and sources.txt.

## Security and integrity
- Content hash (SHA-256) generated from stable report payload.
- Snapshot creation is logged in service logs with case id, version, and hash.
- Versioned endpoints provide immutable references for citations.

## Legal-safe wording
Reports use neutral language and include non-accusatory disclaimers.

## Caching and performance
- Current investigation payload uses cache namespace investigation_page.
- Snapshot generation occurs on first request or explicit refresh.

## Limitations
- PDF generation is dependency-light and intentionally minimal.
- Optional cryptographic signatures for exports can be layered later with a key-management module.
