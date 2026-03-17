# Ingestion Runbook

## Purpose
Operational playbook for resilient ingestion (delta fetch, CAS dedupe, lifecycle tiers, canaries, and manual fallback).

## Quick Triage
1. Check source health via ingestion API.
2. Verify latest run status and parser confidence.
3. Inspect alerts for stale-source, schema drift, duplicate spikes, volume anomalies.
4. If blocked by anti-bot/legal controls, switch to manual ingest and RTI path.

## Daily Checklist
- Confirm `ingestion_success_rate` and `avg_parser_confidence` are within baseline.
- Review `duplicate_rate` and `raw_bytes_ingested` trend.
- Confirm lifecycle movement counts (`archives_moved`) are non-zero for old data.
- Run canary suite and compare schema drift score.

## Incident Patterns
- No success for source > INGEST_ALERT_HOURS:
  - Verify robots policy and source availability.
  - Temporarily reduce fetch cadence.
  - Trigger manual ingestion fallback.
- Parser confidence drop:
  - Pause aggressive parsing for affected source.
  - Run canary + schema detector.
  - Create parser patch and reprocess raw payloads.
- Duplicate rate spike:
  - Check source payload churn and conditional-fetch headers.
  - Validate ETag/Last-Modified handling.

## Manual & RTI Fallback
- Use ingestion API manual upload endpoint for HTML/ZIP/PDF/JSON.
- Generate RTI template for blocked sources and file via institutional workflow.

## Reprocess Procedure
1. Bump parser version.
2. Run reprocess dry-run task and inspect estimated changes.
3. Run full reprocess in batches.
4. Validate normalized output and confidence metrics.

## Escalation Contacts
- On-call engineer: <ONCALL_NAME>
- Data ops lead: <DATA_OPS_LEAD>
- Legal/RTI coordinator: <LEGAL_CONTACT>
- Email group: <TEAM_EMAIL>
