# Defamation-Safe Language & Correction Policy

## Objective

This platform publishes judicial-process data with neutral, evidence-first language. It does not publish accusations as facts and does not imply guilt or intent.

## Label Semantics

- `UNVERIFIED`: Data extracted but not sufficiently corroborated.
- `VERIFIED`: Corroborated by primary source links and adequate confidence.
- `DATA_ANOMALY`: Risky or contradictory content that needs moderation checks.
- `UNUSUAL_DELAY_PATTERN`: Statistical signal only; not a claim of wrongdoing.
- `REQUIRES_VERIFICATION`: Missing/conflicting source context.
- `SENSITIVE`: Content requiring heightened caution.
- `REMOVED`: Content removed from public view.
- `LEGALLY_RESTRICTED`: Access constrained due to legal restrictions.

## Public Language Rules

All public text must pass through `render_public_text()`.

- Use neutral verbs (`shows`, `indicates`, `pattern consistent with`).
- Avoid accusatory conclusions (`proves`, `guilty`, `caused by X`).
- Prefix each public summary with data status and confidence context.
- For unverified/verification-required content, redact names conservatively.
- Quote source snippets and link sources; do not restate allegations as fact.

## Visibility States

- `PUBLIC`: Fully visible to anonymous users.
- `LIMITED`: Public summary only; raw evidence hidden for safety.
- `HIDDEN`: Immediate takedown from anonymous public view.

Raw evidence snapshots are preserved for audit/legal purposes, but not shown publicly when visibility is `LIMITED` or `HIDDEN`.

## Correction Workflow

Endpoints:

- `POST /api/v1/corrections/requests`
- `GET /api/v1/corrections/requests/{id}`
- `GET /api/v1/corrections/admin/corrections/pending`
- `POST /api/v1/corrections/admin/corrections/{id}/assign`
- `POST /api/v1/corrections/admin/corrections/{id}/review`
- `POST /api/v1/corrections/admin/corrections/{id}/publish-response`

SLA targets:

- Acknowledge receipt within 48 hours.
- Review target within 14 days.

Rate limits:

- Per target per month: `RATE_LIMIT_CORRECTION_REQUESTS_PER_TARGET_PER_MONTH`.
- Repeated low-quality submitters may be temporarily blocked and logged.

## Legal Escalation & Takedown

Auto-escalation triggers include legal threat, PII misuse, or takedown demand. Escalated requests may set target visibility to `HIDDEN` pending review.

Takedown protocol:

1. Set `public_status=HIDDEN`.
2. Provide mandatory admin reason.
3. Write `moderation_logs` entry.
4. Notify legal contact workflow.

## Admin Review Runbook Checklist

1. Verify target content and current labels.
2. Check primary source links and snapshot integrity.
3. Evaluate whether text implies unverified allegations.
4. If necessary, redact names and set `LIMITED`.
5. Record decision rationale in `review_notes`.
6. Create moderation log for every sensitive action.
7. Publish neutral public response summary.

## Conservative Redaction Choice

This implementation chooses conservative redaction for unverified paths: names are not auto-revealed by model confidence alone. Any reduced redaction must be an explicit admin-reviewed action.

## Public Response Templates

Auto-acknowledge:

- "We have received your correction request (ID: {id}). This confirms intake only. We aim to acknowledge within 48 hours and review within 14 days."

Accept:

- "Correction accepted. Public content has been updated with a neutral summary and source-linked context."

Reject:

- "Correction request reviewed and not accepted at this stage. Current publication remains label-scoped with evidence context."

Public correction note:

- "Update: A correction request was reviewed. Public text has been adjusted to ensure neutral wording and source-linked context."

## Monitoring & Dashboard Hints

Recommended metrics:

- `justice_tracker_content_labels_total{label=...}`
- `justice_tracker_correction_requests_total{status=...}`
- `justice_tracker_content_takedowns_total{target_type=...}`
- `justice_tracker_legal_escalations_total{reason=...}`
- `justice_tracker_correction_resolution_seconds{status=...}`

PromQL examples:

```promql
sum by (label) (rate(justice_tracker_content_labels_total[1d]))
```

```promql
sum(rate(justice_tracker_content_takedowns_total[1d]))
```

```promql
histogram_quantile(0.9, sum(rate(justice_tracker_correction_resolution_seconds_bucket[7d])) by (le, status))
```

Alert suggestions:

- Trigger warning on sudden spike in `DATA_ANOMALY` labels over baseline.
- Trigger critical alert on takedown spike (`HIDDEN` transitions) within 24h.
- Trigger warning on legal escalations exceeding expected monthly range.
