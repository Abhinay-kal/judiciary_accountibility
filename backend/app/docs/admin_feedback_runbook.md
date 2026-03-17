# Admin Runbook: RtR Feedback and Urgent Legal Requests

## SLA targets
- Acknowledge responder within 48 hours.
- Publish/reject/limit decision within 14 days.
- Urgent legal threat: immediate hide and legal escalation.

## Triage steps
1. Open pending queue: `GET /api/v1/admin/feedback/pending`.
2. Verify claimed affiliation and contact method.
3. Review attachment scan status and LOA evidence.
4. Decide one action:
   - verify + publish
   - publish limited/redacted
   - reject
   - escalate legal

## Urgent legal takedown
1. Call `POST /api/v1/admin/feedback/{id}/urgent-hide` with reason.
2. Call `POST /api/v1/admin/feedback/{id}/escalate` with legal case reference.
3. Notify legal and editor channels.
4. Capture all context in audit payload.

## Redaction guidance
- Remove phone numbers, personal emails, home addresses, ID numbers.
- Keep institutional facts and procedural timeline.
- Do not alter substantive meaning of official statement; preserve full original in immutable record.

## Export for legal request
Include:
- feedback record
- verification entries
- audit log timeline
- attachment metadata and checksums
- moderation notes and reasoned decision

## Abuse handling
- If repeated spam from contact hash, enforce monthly rate limit and note in moderation notes.
- For malicious uploads, block submission and retain checksum evidence.
