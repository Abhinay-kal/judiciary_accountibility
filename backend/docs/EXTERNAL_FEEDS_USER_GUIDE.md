"""
External Feeds Integration System - User Guide

Guide for end users, developers, and administrators using the external feeds system.
"""

# External Feeds User Guide

## What is External Feeds?

External Feeds tracks media and NGO coverage of court cases. For any major case, you can see:
- How widely it's been reported
- Which organizations are covering it
- What the coverage timeline looks like
- Quality/credibility assessment of sources

**Example Use Case:**
> I want to understand public/external interest in case 123/2024. Are credible organizations covering it? How recent is the coverage?

---

## Key Concepts Explained

### Credibility Score (0-1 scale)
**What:** How reliable a source is
**Why:** Helps you focus on trustworthy reporting
**How It Works:**
- Verified sources get higher scores
- Sources with false positives lose points
- Accuracy records improve scores

**Examples:**
- Supreme Court of India: 1.0 (government official source)
- The Hindu: 0.95 (major media with verification)
- Unverified blog: 0.40 (not verified, lower confidence)

### Match Confidence Score (0-1 scale)
**What:** How sure the system is that this article covers THIS specific case
**Why:** Avoids false matches with other cases
**How It Works:**
- Case number match: 0.98 (almost certain)
- Judge name match: 0.75 (pretty confident)
- General court mention: 0.45 (may be other cases too)

**Examples:**
- "Case 123/2024..." mentioned explicitly: 0.98
- "Justice Singh, the judge in case 123..." : 0.85
- "Supreme Court ruled today...": 0.45 (could be any case)

### Verification Status
Four states showing human review:

| Status | Meaning | Symbol |
|--------|---------|--------|
| Auto-Matched | System matched, not yet reviewed | ⚪ |
| Verified | Human confirmed it's relevant | ✓ (green) |
| Disputed | Questionable match | ⚠️ |
| Rejected | False positive, ignore | ✗ (red) |

### Attention Level
Semantic indicator of how much coverage a case has:

| Level | Range | # Articles | Meaning |
|-------|-------|-----------|---------|
| MINIMAL | 0.0-0.2 | 1-2 | Very little coverage |
| LOW | 0.2-0.4 | 3-5 | Light coverage |
| MODERATE | 0.4-0.6 | 6-15 | Regular coverage |
| HIGH | 0.6-0.8 | 16-50 | Significant coverage |
| VERY_HIGH | 0.8-1.0 | 50+ | Extensive coverage |

### Relevance Level
How closely the article covers the case:

| Level | Meaning | Example |
|-------|---------|---------|
| PRIMARY | Direct case coverage | "Supreme Court hears case 123/2024" |
| CONTEXTUAL | Background/history | "Background on judicial reforms..." |
| RELATED | Related but not direct | "Other similar cases at the court..." |
| MINIMAL | Barely relevant | "Supreme Court mentioned" |

---

## How to Use the System

### For Public Users: Accessing Case Coverage

```
Visit: judiciary-accountability.org/cases/{CASE_NUMBER}/media
```

**What You'll See:**

1. **Coverage Summary** (Top of page)
```
Case: 123/2024
External Coverage: 18 articles
Attention Score: 0.72 (HIGH)
Sources: The Hindu, The Wire, Bar Council India, Human Rights Watch

Coverage Timeline: Jan 15 - March 10, 2024 (54 days)
Average Match Confidence: 0.87
Average Source Credibility: 0.92
```

2. **Article List** (Below summary)
```
Title: "Supreme Court Orders Investigation in 123/2024"
Source: The Hindu (✓ Verified)
Published: March 10, 2024
Match Confidence: 0.98
Credibility: 0.95
Summary: The Supreme Court has ordered an investigation...
[Read Full Article]
[View Source Verification Info]
```

3. **Coverage Trends** (Right panel)
- Timeline of articles over time
- Which sources covered it
- Coverage frequency

### For Case Watchers: Following Cases

```
1. Bookmark: /cases/{CASE_NUMBER}/media
2. Check weekly: How much is coverage changing?
3. Look for patterns: Which organizations care most?
4. Cross-reference: Read credible sources for context
```

**Tips:**
- Combine with official court documents for complete picture
- Multiple credible sources (0.75+) = more reliable consensus
- Watch for pattern changes (sudden spike = news event)

### For Researchers: Analyzing Coverage Quality

**Question:** How well different sources cover cases?

```
1. Visit: /api/v1/external-feeds/sources
2. Get list of all sources with credibility scores
3. Compare:
   - The Hindu (0.95): Very reliable
   - Deccan Chronicle (0.88): Reliable
   - Unverified Blog (0.40): Not reliable
```

**Question:** Which cases have the most diverse coverage?

```
1. Visit: /api/v1/external-feeds/stats/coverage
2. Check sources represented & by organization type
3. High diversity = multiple perspective coverage
```

### For Administrators: Managing Coverage

#### Verifying Auto-Matched Articles

**Workflow:**
```
1. Visit Admin Dashboard: /admin/external-feeds/verify
2. Show: Reports with "Auto-Matched" status
3. For each report:
   - Read the article summary
   - Check match confidence
   - Click "Verify" if correct
   - Click "Dispute" if uncertain
   - Click "Reject" if false positive
4. Save feedback
```

**Decision Matrix:**
```
Confidence ≥ 0.85  →  VERIFY (likely correct)
Confidence 0.70-0.85  →  REVIEW SUMMARY (check)
Confidence < 0.70  →  DISPUTE (uncertain)
Clearly wrong match  →  REJECT (false positive)
```

#### Monitoring Source Quality

**Monthly Quality Review:**
```
1. Visit: /admin/external-feeds/sources
2. Check quality metrics for each source:
   - False positive rate
   - Duplicate rate
   - Accuracy rate
3. If false positive rate > 20%:
   - Review recent matches
   - Reduce credibility score
   - Add notes about issues
4. If false positive rate < 5%:
   - Increase credibility score (performance reward)
```

#### Handling Disputed Reports

**When Report is Disputed:**
```
1. Read article carefully
2. Check against case details
3. Look at match confidence breakdown
4. Decision:
   - Actually relevant? → Verify
   - Clearly not? → Reject
   - Uncertain? → Mark for expert legal review
```

---

## API Reference

### Quick Start

```python
import requests

# Get case coverage
response = requests.get(
    "https://api.judiciary.org/api/v1/external-feeds/cases/123/2024/media",
    params={"verified_only": True, "limit": 20}
)

case_media = response.json()
print(f"Case {case_media['case_id']} has {case_media['total_reports']} articles")
```

### GET /cases/{case_id}/media

**Returns:** All external media coverage for case

**Parameters:**
```
case_id (path): Case number, e.g., "123/2024"
verified_only (query): Boolean, default=False
  - true: Only manually verified matches
  - false: Show all matches
limit (query): Results per page, default=20, max=100
offset (query): Pagination offset, default=0
```

**Response:**
```json
{
  "case_id": "123/2024",
  "total_reports": 18,
  "verified_reports": 14,
  "external_attention_score": 0.72,
  "attention_level": "HIGH",
  "sources": ["The Hindu", "The Wire", "Bar Council India"],
  "date_range": {
    "earliest": "2024-01-15T10:30:00",
    "latest": "2024-03-10T14:45:00"
  },
  "average_confidence": 0.87,
  "average_credibility": 0.92,
  "reports": [
    {
      "report_id": "rpt_123_the_hindu_1",
      "case_id": "123/2024",
      "source_id": "the_hindu",
      "source_name": "The Hindu",
      "title": "Supreme Court Orders Investigation",
      "url": "https://thehindu.com/...",
      "publication_date": "2024-03-10T14:45:00",
      "match_confidence": 0.98,
      "credibility_score": 0.95,
      "relevance_level": "PRIMARY",
      "verification_status": "manually_verified",
      "summary": "The Supreme Court has ordered investigation..."
    }
  ]
}
```

### GET /sources

**Returns:** List of media sources

**Parameters:**
```
organization_type (query): Filter by type
  - MEDIA: News organizations
  - NGO: Non-governmental organizations
  - GOVERNMENT: Official sources
  - RESEARCH: Research institutions
  - LEGAL_WATCHDOG: Legal monitoring groups
verified_only (query): Boolean, show only verified
limit (query): Results per page, default=100, max=500
offset (query): Pagination offset
```

**Response:**
```json
{
  "total_sources": 127,
  "credibility_score_average": 0.87,
  "sources": [
    {
      "source_id": "the_hindu",
      "name": "The Hindu",
      "organization_type": "MEDIA",
      "credibility_score": 0.95,
      "verification_status": "verified",
      "language": "en",
      "geographic_scope": ["India"]
    },
    {
      "source_id": "amnesty_intl",
      "name": "Amnesty International",
      "organization_type": "NGO",
      "credibility_score": 0.94,
      "verification_status": "verified",
      "language": "en",
      "geographic_scope": ["Global"]
    }
  ]
}
```

### GET /cases/{case_id}/attention-score

**Returns:** External attention/coverage score

**Response:**
```json
{
  "case_id": "123/2024",
  "attention_score": 0.72,
  "attention_level": "HIGH",
  "total_articles": 18,
  "credible_sources": 14,
  "coverage_span_days": 54,
  "most_recent_coverage": "2024-03-10T14:45:00"
}
```

### GET /reports/{report_id}/summary

**Returns:** Single report with AI-generated summary

**Response:**
```json
{
  "report_id": "rpt_123_the_hindu_1",
  "case_id": "123/2024",
  "source_name": "The Hindu",
  "title": "Supreme Court Orders Investigation",
  "url": "https://thehindu.com/...",
  "publication_date": "2024-03-10T14:45:00",
  "match_confidence": 0.98,
  "credibility_score": 0.95,
  "relevance_level": "PRIMARY",
  "verification_status": "manually_verified",
  "summary_text": "The Supreme Court of India has ordered an investigation into case 123/2024...",
  "key_facts": [
    "Supreme Court ordered investigation",
    "Justice Singh presided",
    "Hearing scheduled for next month"
  ],
  "parties": ["Plaintiff", "Defendant"],
  "courts": ["Supreme Court of India"],
  "dates": ["2024-03-10", "2024-04-15"]
}
```

### POST /reports/{report_id}/verify

**Action:** Manually verify a report

**Body:**
```json
{
  "verified_by": "reviewer@judiciary.org",
  "relevance_level": "PRIMARY",
  "notes": "Confirmed - case number clearly mentioned"
}
```

**Response:**
```json
{
  "success": true,
  "report_id": "rpt_123_the_hindu_1",
  "verification_status": "manually_verified",
  "verified_by": "reviewer@judiciary.org",
  "verified_at": "2024-03-11T09:30:00"
}
```

### GET /stats/coverage

**Returns:** System-wide statistics

**Response:**
```json
{
  "total_reports": 2847,
  "cases_with_coverage": 156,
  "sources_represented": 42,
  "verification_breakdown": {
    "auto_matched": 1200,
    "manually_verified": 1400,
    "disputed": 150,
    "rejected": 97
  },
  "relevance_breakdown": {
    "primary": 1600,
    "contextual": 800,
    "related": 350,
    "minimal": 97
  },
  "average_match_confidence": 0.85
}
```

---

## Interpreting the Data

### Coverage Score: What Does 0.72 Mean?

The attention score of 0.72 (HIGH) means:
- **14** verified credible sources covering the case
- **18 total** articles from different organizations
- Coverage spanning **54 days**
- Average match confidence **87%** (likely accurate)
- Average source credibility **92%** (highly trusted)

**Translation:** This case has significant, sustained coverage from trusted sources.

### Match Confidence: What Does 0.98 Mean?

When an article has 0.98 match confidence:
- **Strategy Used:** Case number matching (explicit "123/2024" in article)
- **Certainty:** 98% sure this article is about THIS case
- **Interpretation:** Very high confidence, likely accurate

**Comparison:**
- 0.98: Case number explicitly mentioned
- 0.85: Party names + judge mentioned
- 0.70: Keywords + timing suggest match
- 0.45: General court mention (could be other cases)
- 0.30: Marginal confidence (needs verification)

### Source Credibility: What Does 0.95 Mean?

When The Hindu has 0.95 credibility:
- **Basis:** Verified media organization
- **Track Record:** <5% false positive rate
- **Coverage Quality:** Accurate legal reporting
- **Penalty:** None recent (no recent errors)

**Decision:** You can generally trust reporting from this source

---

## Common Scenarios

### Scenario 1: I See a Case with HIGH Attention Score

**What This Means:**
- Multiple credible organizations covering it
- Sustained media interest
- Likely important case affecting society
- Public interest justified

**What To Do:**
1. Read articles from most credible sources (0.95+ score)
2. Look for consensus across sources
3. Read official court documents too
4. Form informed opinion based on diverse sources

### Scenario 2: I See a Report with LOW Match Confidence (0.45)

**What This Means:**
- Uncertain if article really covers this case
- General court mention without case specifics
- May be false positive
- Requires human verification

**What To Do:**
1. Check if it's verified (green checkmark)
2. If verified = human confirmed it's accurate
3. If not verified = take with caution
4. Click "View Details" to read the article

### Scenario 3: A New Case With NO External Coverage

**What This Means:**
- Early stage case (few days old)
- Minor case (limited public interest)
- Not reported by tracked sources
- May become covered later

**What To Do:**
1. Check media sources regularly
2. Coverage may appear as case progresses
3. Set bookmark to monitor
4. Check case status in official system

### Scenario 4: Rapid Change In Coverage

**What This Means:**
- Major news event occurred
- Case became high-profile
- New development
- Public interest increased

**Example:**
- Case 456/2023: 2 articles (low attention: 0.2)
- → Court made major ruling
- → Suddenly 15 articles (high attention: 0.7)

**What To Do:**
1. Check most recent articles
2. Understand what changed
3. Look at credible sources for analysis
4. Verify claims independently

---

## Troubleshooting

### Q: Why doesn't my case appear in the system?

**A:** Possible reasons:
1. **No coverage yet** – Case is new or not publicly reported
2. **Coverage exists but not ingested** – Sources may not be in our list yet
3. **No case number mention** – System may not have matched articles yet
4. **False matches rejected** – Automated removal of non-matches

**Solution:**
- Wait for coverage to develop
- Provide case number explicitly
- Request source addition (contact feedback@judiciary.org)

### Q: Why is this article matched with LOW confidence?

**A:** Possible reasons:
1. **Case not explicitly mentioned** – General court/judge mention only
2. **One matching strategy only** – Not multiple confirming factors
3. **Ambiguous content** – Could potentially be other cases

**Solution:**
- Check if match is manually verified (green checkmark = trusted)
- Read article summary to assess relevance
- Report if it's a false positive

### Q: Why is this source's credibility so low?

**A:** Possible reasons:
1. **Unverified organization** – Not yet verified by jury
2. **High false positive rate** – Many wrong matches in past
3. **Low accuracy rate** – Reporting errors detected
4. **Recent issues** – Recent problems temporarily lowered score

**Solution:**
- Treat low-credibility sources with extra caution
- Cross-check claims with verified sources
- Report significant errors for review

---

## Privacy & Fairness

### What Data is Collected?

- **Article URLs, titles, publication dates** (public information)
- **Source organization information** (public information)
- **Match confidence and verification status** (automated/human review)
- **No personal information** from articles

### Is This Fair to Parties in Cases?

**Design Principles:**
- **Neutral presentation:** No opinions, just facts
- **Source credibility:** Only show verified reporting
- **Balanced coverage:** Show all significant coverage
- **Verification required:** Human review before prominence

**Protections:**
- Defamatory language detected and flagged
- Opinion articles marked as such
- False matches removed via dispute process
- Credible sources preferred

### Can I Correct Errors?

**Yes:**
1. If you find a false match → Click "Dispute"
2. If you find defamatory language → Report to admin
3. If summary is inaccurate → Flag for review
4. Contact: feedback@judiciary-accountability.org

---

## Advanced Usage

### For Lawyers: Case Law Research

```python
# Get all cases with specific source coverage
import requests

# Example: Find all cases covered by Amnesty International
response = requests.get(
    "https://api.judiciary.org/api/v1/external-feeds/sources/amnesty_intl"
)

amnesty_source = response.json()
# Then query each case for amnesty coverage
```

### For Researchers: Tracking Coverage Patterns

```python
# Get coverage statistics
response = requests.get(
    "https://api.judiciary.org/api/v1/external-feeds/stats/coverage"
)

stats = response.json()

# Analyze:
# - How many cases have external coverage? (cases_with_coverage)
# - What % are manually verified? (verification_breakdown)
# - Which sources are most active? (aggregate by source_id)
# - What's the average quality? (average_confidence, average_credibility)
```

### For Data Analysts: Building on the API

```python
# Export all case coverage to CSV
import csv
import requests

all_cases = requests.get("https://api.judiciary.org/api/v1/cases/list").json()

with open('case_coverage.csv', 'w') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'case_id', 'total_reports', 'verified_reports',
        'attention_score', 'attention_level', 'average_confidence'
    ])
    writer.writeheader()
    
    for case in all_cases:
        response = requests.get(
            f"https://api.judiciary.org/api/v1/external-feeds/cases/{case['id']}/media/summary"
        )
        if response.status_code == 200:
            writer.writerow(response.json())
```

---

## Frequently Asked Questions

**Q: Is this system biased toward certain sources?**
A: No. We use credibility scoring to weight sources, but all verified sources are included equally.

**Q: Can I submit my own coverage?**
A: Not yet, but we're building this feature. Current sources are verified beforehand.

**Q: How often is coverage updated?**
A: Automated ingestion runs daily. New articles appear within 24 hours of publication.

**Q: Can I request a new source be added?**
A: Yes! Email: coverage-sources@judiciary.org with source details.

**Q: Is this system affiliated with the court?**
A: No. This is an independent transparency initiative. Data is derived from public sources.

**Q: Can I use this data for publications?**
A: Yes, please cite appropriately. Attribution: "Judiciary Accountability External Feeds"

---

## Support

- **Tech Issues:** support@judiciary-accountability.org
- **Data Questions:** data@judiciary-accountability.org
- **Coverage Questions:** coverage@judiciary-accountability.org
- **GitHub:** github.com/judiciary-accountability/external-feeds

---

**Last Updated:** March 18, 2026
**Version:** 1.0.0
**Status:** Live
