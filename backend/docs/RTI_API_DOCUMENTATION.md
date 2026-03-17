# RTI Request Generator - API Documentation

## Quick Start

**Base URL:** `https://api.judiciary-accountability.in/rti`

**Authentication:** Not required for RTI endpoints (public transparency API)

**Rate Limiting:** 100 requests/minute per IP

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication & Security](#auth)
3. [Response Format](#response-format)
4. [Error Handling](#error-handling)
5. [Endpoint Reference](#endpoints)
   - [Templates](#templates)
   - [Authority Lookup](#authority)
   - [RTI Generation](#generation)
   - [Validation](#validation)
   - [Export](#export)
   - [Tracking](#tracking)
   - [Statistics](#statistics)
6. [Code Examples](#examples)

---

## Overview

The RTI Request Generator API enables programmatic:
- Generation of RTI requests from case details
- Authority lookup (finding correct PIO)
- Legal compliance validation
- Export to multiple formats
- Tracking of RTI submissions

**Use Cases:**
- Integrate RTI generation into case management systems
- Build RTI bots for common request types
- Analyze RTI request patterns
- Bulk generate RTI requests for legal aid organizations

---

## Authentication & Security

### Public Endpoints (No Auth Required)

- `GET /rti/templates`
- `GET /rti/health`
- `POST /rti/validate`

### Protected Endpoints (Optional User ID)

Other endpoints require optional user context but work anonymously.

### Rate Limiting

```
Limit: 100 requests/minute
       2000 requests/day
Scope: Per IP address
Status Code: 429 (Too Many Requests)
```

### Security Headers

All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

---

## Response Format

All responses use JSON format.

### Success Response (200 OK)

```json
{
  "status": "success",
  "data": {
    // Response data based on endpoint
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123xyz"
}
```

### Error Response (4xx/5xx)

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Description of what went wrong",
    "details": {
      "field": "Additional error details"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123xyz"
}
```

### Common Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| `INVALID_REQUEST` | 400 | Malformed request |
| `MISSING_FIELD` | 400 | Required field missing |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_FAILED` | 422 | Request validation failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `SERVER_ERROR` | 500 | Internal server error |

---

## Endpoint Reference

---

## GET `/rti/templates`

List all available RTI request templates.

### Request

```bash
curl -X GET "https://api.judiciary-accountability.in/rti/templates"
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": [
    {
      "request_type": "MISSING_RECORDS",
      "description": "Request for missing or unavailable court documents",
      "use_case": "When court documents are lost or not available",
      "sections": [
        "applicant_details",
        "authority_address",
        "subject_line",
        "information_requested",
        "declaration",
        "contact_details"
      ]
    },
    {
      "request_type": "TRANSFER_HISTORY",
      "description": "Request for case transfer history between courts",
      "use_case": "When case has been transferred to different court",
      "sections": [
        "applicant_details",
        "authority_address",
        "subject_line",
        "information_requested",
        "declaration",
        "contact_details"
      ]
    },
    // ... more templates
  ],
  "count": 7
}
```

### Template Types

| Type | Purpose |
|------|---------|
| `MISSING_RECORDS` | Recover lost or unavailable documents |
| `TRANSFER_HISTORY` | Track case movements between courts |
| `TRANSCRIPTS` | Obtain hearing recordings/transcripts |
| `PENDING_ORDERS` | Get status of pending orders |
| `CASE_LISTING` | List all cases of specific party |
| `ADMINISTRATIVE_DELAYS` | Investigate case postponements |
| `DISCREPANCIES` | Clarify inconsistencies in records |

---

## POST `/rti/authority/lookup`

Find Public Information Officer (PIO) for specific court jurisdiction.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/authority/lookup" \
  -H "Content-Type: application/json" \
  -d '{
    "court_level": "DISTRICT_COURT",
    "state": "MAHARASHTRA",
    "jurisdiction": "Mumbai"
  }'
```

### Request Body

```json
{
  "court_level": "DISTRICT_COURT",  // Required: DISTRICT_COURT, HIGH_COURT, SUPREME_COURT
  "state": "MAHARASHTRA",           // Required: Indian state/UT name
  "jurisdiction": "Mumbai"          // Optional: District or circuit
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "pio_id": "pio_mh_dc_001",
    "pio_name": "Shri Ram Kumar Sharma",
    "pio_email": "pio@mumbaidistrictcourt.gov.in",
    "pio_phone": "+91-22-6121-2121",
    "office_address": "District Court, Mumbai, Maharashtra 400001",
    "designation": "Office Superintendent",
    "court_level": "DISTRICT_COURT",
    "state": "MAHARASHTRA"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `pio_id` | string | Unique identifier for PIO |
| `pio_name` | string | Full name of PIO |
| `pio_email` | string | Email for RTI submissions |
| `pio_phone` | string | Phone number |
| `office_address` | string | Complete office address |
| `designation` | string | Job title/designation |
| `court_level` | string | Court hierarchy level |
| `state` | string | State/UT |

### Error: Not Found (404)

```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "PIO not found for jurisdiction",
    "details": {
      "court_level": "DISTRICT_COURT",
      "state": "MAHARASHTRA"
    }
  }
}
```

---

## POST `/rti/generate`

Generate complete RTI request from case and applicant details.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "MISSING_RECORDS",
    "case_details": {
      "case_number": "123/2023",
      "case_year": 2023,
      "court_name": "District Court, Mumbai",
      "court_level": "DISTRICT_COURT",
      "state": "maharashtra",
      "judge_name": "Justice Ramesh Kumar",
      "case_status": "pending"
    },
    "applicant_info": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "9876543210",
      "address": "123 Main Street",
      "city": "Mumbai",
      "state": "maharashtra",
      "pincode": "400001",
      "language": "english"
    },
    "information_needs": "Request certified copy of judgment order dated 15-Jan-2023",
    "urgency": "regular"
  }'
```

### Request Body

```json
{
  "request_type": "string",      // Required: From templates
  "case_details": {              // Required
    "case_number": "string",     // e.g., "123/2023"
    "case_year": number,         // e.g., 2023
    "court_name": "string",      // Full court name
    "court_level": "string",     // DISTRICT_COURT, HIGH_COURT, SUPREME_COURT
    "state": "string",           // State name
    "judge_name": "string",      // Optional: Judge's name
    "case_status": "string"      // Optional: pending, disposed, appealed
  },
  "applicant_info": {            // Required
    "name": "string",            // Full legal name
    "email": "string",           // Valid email
    "phone": "string",           // Phone number
    "address": "string",         // Residential/office address
    "city": "string",            // City name
    "state": "string",           // State
    "pincode": "string",         // ZIP/postal code
    "language": "string"         // Language preference
  },
  "information_needs": "string", // What information needed
  "urgency": "string"            // Optional: regular, urgent
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "request_id": "rti_5f7f8a9b-1234-5678-9abc-def012345678",
    "status": "draft",
    "request_type": "MISSING_RECORDS",
    "case_number": "123/2023",
    "court_name": "District Court, Mumbai",
    "state": "maharashtra",
    "pio_name": "Shri Ram Kumar Sharma",
    "subject_line": "RTI Request - Request for missing court records (Case No. 123/2023)",
    "body_preview": "I am writing to request information under the Right to Information Act, 2005...",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique tracking ID for this RTI |
| `status` | string | Current status: draft, submitted, acknowledged, etc. |
| `request_type` | string | Type of RTI request |
| `case_number` | string | Associated case number |
| `court_name` | string | Court handling the case |
| `state` | string | State jurisdiction |
| `pio_name` | string | Name of assigned PIO |
| `subject_line` | string | Email subject recommended |
| `body_preview` | string | First 200 chars of generated RTI |
| `created_at` | timestamp | When RTI was created |

---

## POST `/rti/validate`

Validate RTI request for legal compliance.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "request_content": "I request certified copy of judgment order dated 15-Jan-2023",
    "request_type": "MISSING_RECORDS",
    "applicant_email": "john@example.com"
  }'
```

### Request Body

```json
{
  "request_content": "string",  // RTI request text
  "request_type": "string",     // Type of request
  "applicant_email": "string"   // Optional: Applicant email
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "compliance_score": 95
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | boolean | Whether request passes validation |
| `errors` | array | Critical issues (prevent submission) |
| `warnings` | array | Warnings (but submission allowed) |
| `compliance_score` | number | 0-100 compliance rating |

### Example Error Response

```json
{
  "status": "success",
  "data": {
    "is_valid": false,
    "errors": [
      "Request contains accusatory language: 'dishonest'",
      "Request is too vague: 'all information about case'"
    ],
    "warnings": [
      "Consider specifying exact documents needed",
      "Request might take longer due to breadth"
    ],
    "compliance_score": 45
  }
}
```

---

## POST `/rti/export`

Export RTI request to desired format.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/export" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "rti_5f7f8a9b-1234-5678-9abc-def012345678",
    "format": "pdf"
  }'
```

### Request Body

```json
{
  "request_id": "string",  // RTI request ID from /generate
  "format": "string"       // pdf, docx, text, postal, email
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "success": true,
    "format": "pdf",
    "filename": "RTI_123-2023_20240115.pdf",
    "size_bytes": 45678,
    "download_url": "/rti/download/rti_5f7f8a9b-1234-5678-9abc-def012345678?format=pdf"
  }
}
```

### Supported Formats

| Format | Use | Output |
|--------|-----|--------|
| `pdf` | Professional appearance, email submission | PDF file |
| `docx` | Editable in Word, modifications | Word document |
| `text` | Plain text, copying into email | Text content |
| `postal` | Print and mail, official appearance | PDF with postal layout |
| `email` | Direct paste into email, no attachment | Formatted text |

---

## POST `/rti/track`

Create tracking record for RTI submission.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/track" \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "MISSING_RECORDS",
    "case_number": "123/2023",
    "case_year": 2023,
    "court_name": "District Court, Mumbai",
    "state": "maharashtra",
    "applicant_email": "john@example.com",
    "applicant_name": "John Doe"
  }'
```

### Request Body

```json
{
  "request_type": "string",      // Required
  "case_number": "string",       // Required
  "case_year": number,           // Required
  "court_name": "string",        // Required
  "state": "string",             // Required
  "applicant_email": "string",   // Optional
  "applicant_name": "string"     // Optional
}
```

### Response (201 Created)

```json
{
  "status": "success",
  "data": {
    "request_id": "rti_5f7f8a9b-1234-5678-9abc-def012345678",
    "status": "draft",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

## GET `/rti/track/{request_id}`

Get tracking status of specific RTI request.

### Request

```bash
curl -X GET "https://api.judiciary-accountability.in/rti/track/rti_5f7f8a9b-1234-5678-9abc-def012345678"
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "request_id": "rti_5f7f8a9b-1234-5678-9abc-def012345678",
    "case_number": "123/2023",
    "court_name": "District Court, Mumbai",
    "state": "maharashtra",
    "status": "submitted",
    "date_created": "2024-01-10T09:00:00Z",
    "date_submitted": "2024-01-12T14:30:00Z",
    "date_acknowledged": null,
    "date_responded": null,
    "response_is_complete": false,
    "denial_reason": null,
    "appeal_filed": false
  }
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `draft` | Created but not yet submitted |
| `submitted` | Sent to PIO, awaiting acknowledgment |
| `acknowledged` | PIO acknowledged, now reviewing |
| `under_review` | PIO actively processing |
| `response_partial` | Partial information provided |
| `response_full` | Complete response received |
| `response_denied` | Request denied |
| `appeal_filed` | First appeal submitted |
| `closed` | Case closed/resolved |
| `expired` | Response deadline passed |

---

## POST `/rti/track/{request_id}/submit`

Record that RTI has been officially submitted to PIO.

### Request

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/track/rti_5f7f8a9b-1234-5678-9abc-def012345678/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "submission_mode": "email",
    "submission_reference": "email-tracking-12345"
  }'
```

### Request Body

```json
{
  "submission_mode": "string",          // postal, email, online, hand-delivered
  "submission_reference": "string"      // Optional: tracking number or reference
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "success": true,
    "message": "Submission recorded"
  }
}
```

---

## GET `/rti/statistics`

Get system-wide RTI statistics.

### Request

```bash
curl -X GET "https://api.judiciary-accountability.in/rti/statistics"
```

### Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "total_requests": 1247,
    "by_status": {
      "draft": 234,
      "submitted": 156,
      "acknowledged": 89,
      "under_review": 112,
      "response_partial": 211,
      "response_full": 334,
      "response_denied": 78,
      "appeal_filed": 23,
      "closed": 10
    },
    "denial_reasons": {
      "third_party_privacy": 28,
      "frivolous": 18,
      "vague": 15,
      "information_does_not_exist": 12,
      "other": 5
    },
    "appeals_filed": 23,
    "average_response_time_days": 22.5
  }
}
```

---

## GET `/rti/health`

Health check endpoint for RTI service.

### Request

```bash
curl -X GET "https://api.judiciary-accountability.in/rti/health"
```

### Response (200 OK)

```json
{
  "status": "healthy",
  "service": "RTI Request Generator",
  "version": "1.0.0"
}
```

---

## Code Examples

### Python Example: Generate and Export RTI

```python
import requests
import json

API_BASE = "https://api.judiciary-accountability.in/rti"

# 1. Generate RTI
response = requests.post(f"{API_BASE}/generate", json={
    "request_type": "MISSING_RECORDS",
    "case_details": {
        "case_number": "123/2023",
        "case_year": 2023,
        "court_name": "District Court, Mumbai",
        "court_level": "DISTRICT_COURT",
        "state": "maharashtra"
    },
    "applicant_info": {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "9876543210",
        "address": "123 Main St",
        "city": "Mumbai",
        "state": "maharashtra",
        "pincode": "400001",
        "language": "english"
    },
    "information_needs": "Certified copy of judgment"
})

rti_data = response.json()["data"]
request_id = rti_data["request_id"]

print(f"RTI Generated: {request_id}")
print(f"Status: {rti_data['status']}")

# 2. Export to PDF
export_response = requests.post(f"{API_BASE}/export", json={
    "request_id": request_id,
    "format": "pdf"
})

export_data = export_response.json()["data"]
print(f"PDF File: {export_data['filename']}")
print(f"Download: {export_data['download_url']}")

# 3. Track Status
track_response = requests.get(f"{API_BASE}/track/{request_id}")
track_data = track_response.json()["data"]
print(f"Current Status: {track_data['status']}")
```

### JavaScript Example: Lookup PIO

```javascript
const API_BASE = "https://api.judiciary-accountability.in/rti";

async function findPIO(courtLevel, state) {
  const response = await fetch(`${API_BASE}/authority/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      court_level: courtLevel,
      state: state
    })
  });
  
  const data = await response.json();
  
  if (data.status === "success") {
    const pio = data.data;
    console.log(`PIO: ${pio.pio_name}`);
    console.log(`Email: ${pio.pio_email}`);
    console.log(`Address: ${pio.office_address}`);
    return pio;
  } else {
    console.error("PIO not found");
    return null;
  }
}

// Usage
findPIO("DISTRICT_COURT", "MAHARASHTRA");
```

### CURL Example: Validate RTI

```bash
curl -X POST "https://api.judiciary-accountability.in/rti/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "request_content": "I humbly request certified copy of the judgment order dated 15 January 2023, case number 123 of 2023",
    "request_type": "MISSING_RECORDS",
    "applicant_email": "john@example.com"
  }' | jq .
```

---

## Error Handling Best Practices

### Try-Catch Pattern

```javascript
try {
  const response = await fetch(`${API_BASE}/track/${requestId}`);
  
  if (!response.ok) {
    const error = await response.json();
    console.error(`Error ${response.status}:`, error.error.message);
    throw new Error(error.error.code);
  }
  
  const tracking =await response.json();
  return tracking.data;
  
} catch (err) {
  console.error("Failed to fetch tracking status:", err.message);
  // Handle gracefully
}
```

### Common Issues & Solutions

| Issue | Status | Solution |
|-------|--------|----------|
| PIO not found | 404 | Verify court name and state spelling |
| Invalid request format | 400 | Check required fields in request body |
| Rate limited | 429 | Wait 60 seconds before retrying |
| Server error | 500 | Retry after 5 minutes |

---

## Webhooks (Future)

Future version will support webhooks for:
- RTI status changes
- Responses received
- Appeals filed
- Denial notifications

---

## API Versioning

Current Version: **v1**  
URL Scheme: `/rti/v1/endpoints`

Future versions will maintain backward compatibility or provide migration guide.

---

## Support & Feedback

- **Documentation:** https://docs.judiciary-accountability.in/rti
- **Issues:** https://github.com/judiciary-accountability/rti-generator/issues
- **Email:** api-support@judiciary-accountability.in
- **Chat:** Available on documentation site

---

**Last Updated:** January 2024  
**API Version:** 1.0.0  
**Status:** Production Ready
