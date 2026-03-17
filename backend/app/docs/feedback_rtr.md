# Right-to-Respond (RtR) Feedback Mechanism

## Purpose
The RtR mechanism provides an auditable channel for officials and named entities to submit responses tied to a case record.

## Public flow
1. Authorized responder submits response at `POST /api/v1/feedback/case/{case_id}`.
2. System stores immutable record in `case_feedback` with `public_status=PENDING_REVIEW`.
3. Verification token is sent to responder contact.
4. After verification and moderation, admin publishes response.
5. Public case page shows the response card with verification badge and public note.

## Verification methods (recommended order)
1. `email_token`: low-friction default (48h expiry).
2. `domain_verification`: trusted domain plus admin review.
3. `letter_of_authority`: uploaded LOA reviewed by admin.
4. `admin_verified`: manual checks (directory/phone).
5. `oauth_provider`: optional external identity integration.

## Moderation checklist
- Confirm claimed affiliation is plausible for responder type.
- If public mailbox used for official claim, require LOA or manual verification.
- Sanitize response text and redact sensitive personal data.
- Review attachments and malware scan status.
- Write clear neutral `public_note`.
- Log action reason for every decision.

## Public wording templates
- Verified:
  - "An official response was submitted by [affiliation] on [date]. This response has been verified via [method]."
- Pending:
  - "A response has been submitted and is pending verification. We will update when verified."

## Notification templates
- Token sent:
  - "We received your response. Please verify ownership using the one-time link."
- Verified:
  - "Your response has been verified and is queued for moderation."
- Published:
  - "Your response has been published with verification status and attachments policy."
- Rejected/Limited:
  - "Your response was reviewed and [rejected/published in limited form]. Reason: [reason]."

## Legal escalation process
- Use `/api/v1/admin/feedback/{id}/escalate` when legal risk is identified.
- Use `/api/v1/admin/feedback/{id}/urgent-hide` for immediate legal threat suppression.
- Every escalation/urgent hide must create audit log and notify legal contact.

## Privacy and retention
- Responder contact is stored tokenized (base64 + hash comparison path).
- Public rendering withholds names until verified/published.
- Full audit records are retained for legal accountability.

## Monitoring queries and sample alerts
- Pending queue length:
```promql
justice_tracker_feedback_pending_queue
```
- Publish throughput:
```promql
sum by (action) (rate(justice_tracker_feedback_moderation_actions_total[1h]))
```
- Verification failures:
```promql
sum(rate(justice_tracker_feedback_verifications_total{result="failed"}[30m]))
```
- Average approval time:
```promql
histogram_quantile(0.5, sum(rate(justice_tracker_feedback_approval_seconds_bucket[6h])) by (le))
```

Sample alerts:
- `RtRPendingQueueHigh`: queue > 25 for 30m.
- `RtRApprovalSlaBreached`: p50 approval > 14 days.
- `RtRVerificationFailureSpike`: failed verifications > 20/hour.
