# Case Importance Scoring

## Overview

The importance subsystem computes a case-level score in `[0,1]` with confidence and interpretable components.

### Core fields

- `cases.importance_score`
- `cases.importance_confidence`
- `cases.importance_components`
- `cases.last_scored_at`
- `cases.importance_override`

### Supporting tables

- `case_media_mentions`
- `importance_configs`
- `importance_audit_logs`

## Scoring components

Weighted components in `CaseImportanceScorer`:

- politician link confidence
- corruption keyword density in text
- case type mapping
- media mentions with credibility/recency decay
- monetary value (log-normalized, capped)
- judicial priority signal
- historical public interest

Anti-gaming controls:

- corruption density normalization cap
- media burst cap for low-credibility recent mentions
- confidence penalty when anti-gaming caps trigger

## Execution paths

1. Fast-pass: ingestion path (`upsert_case_from_normalized`) computes quick score without media lookup.
2. Full recompute: Celery daily task (`app.tasks.importance_recompute.recompute_case_importance`) recomputes stale cases.

## API

### Case APIs

- `GET /api/v1/cases?min_importance=0.7`
- `GET /api/v1/cases/{case_id}` includes importance fields.

### Admin APIs

- `GET /api/v1/admin/importance/config`
- `PUT /api/v1/admin/importance/config`
- `POST /api/v1/admin/importance/{case_id}/override`

## Environment variables

- `IMPORTANCE_WEIGHTS_JSON`
- `IMPORTANCE_MIN_CONFIDENCE`
- `IMPORTANCE_MEDIA_DECAY_LAMBDA`
- `IMPORTANCE_MONETARY_CAP`
- `IMPORTANCE_MIN_CASE_SIGNALS`
- `IMPORTANCE_FASTPASS_ENABLED`
- `IMPORTANCE_DAILY_BATCH_SIZE`

## Frontend snippet

```tsx
<div className="importance-chip" title={caseItem.importance_components?.explanation || ""}>
  <span>Importance</span>
  <strong>{(caseItem.importance_score ?? 0).toFixed(2)}</strong>
  <em>conf {(caseItem.importance_confidence ?? 0).toFixed(2)}</em>
</div>
```
