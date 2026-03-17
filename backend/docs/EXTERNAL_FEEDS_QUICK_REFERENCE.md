"""
External Feeds Integration System - Quick Reference Card
One-page reference for developers and operators
"""

# External Feeds - Quick Reference

## Module Overview (9 Modules)

| Module | Purpose | Key Classes | Input | Output |
|--------|---------|------------|-------|--------|
| **sources.py** | Source registry & credibility | SourceRegistry, SourceMetadata | Organization info | Credibility score (0-1) |
| **ingestion.py** | Collect articles | IngestionPipeline, RawArticle | RSS/APIs/manual | Article + hash |
| **entity_matching.py** | Link to cases | CaseMatchingEngine, MatchCandidate | Article content | Match confidence (0-1) |
| **deduplication.py** | Find duplicates | DeduplicationEngine, DuplicateGroup | Articles | Duplicate type + group ID |
| **credibility.py** | Score attention | CredibilityModel, ExternalAttentionScore | Matched articles | Attention score (0-1) |
| **linking.py** | Case-article link | ExternalReportLinkingEngine, ExternalReport | Match + score | Database record |
| **summarization.py** | Generate summary | SummarizationEngine, ArticleSummary | Full text | Neutral summary |
| **api.py** | REST endpoints | ExternalFeedsAPIRouter | HTTP request | JSON response |
| **tests/** | Validation | 8 test classes | Module instances | 40+ test results |

---

## Confidence Scores Quick Guide

### Match Confidence (Entity Matching)
- **0.98**: Case number "123/2024" explicitly mentioned
- **0.85**: Party names + court identified
- **0.75**: Judge name + court mentioned
- **0.60**: Keywords suggest association (fuzzy)
- **0.45**: General court mention (unprecise)

### Source Credibility (Sources Registry)
- **1.0**: Government official (Supreme Court)
- **0.95**: Major media (The Hindu, The Wire)
- **0.88**: Regional media (Deccan Chronicle)
- **0.93**: International NGO (HRW, Amnesty)
- **0.40**: Unverified source

### Attention Score (Credibility Model)
- **0.8-1.0**: VERY_HIGH (50+ articles, multiple types)
- **0.6-0.8**: HIGH (16-50 articles, diverse sources)
- **0.4-0.6**: MODERATE (6-15 articles)
- **0.2-0.4**: LOW (3-5 articles)
- **0.0-0.2**: MINIMAL (1-2 articles)

---

## API Endpoints (8 Total)

```
GET  /api/v1/external-feeds/sources
     → List all sources with credibility scores
     
GET  /api/v1/external-feeds/sources/{source_id}
     → Single source details
     
GET  /api/v1/external-feeds/cases/{case_id}/media
     → All articles for case (paginated)
     Query: verified_only=true, limit=20, offset=0
     
GET  /api/v1/external-feeds/cases/{case_id}/attention-score
     → Case attention metrics and level
     
GET  /api/v1/external-feeds/reports/{report_id}
     → Single report with all metadata
     
GET  /api/v1/external-feeds/reports/{report_id}/summary
     → Report with AI-generated summary
     
POST /api/v1/external-feeds/reports/{report_id}/verify
     Body: {verified_by, relevance_level, notes}
     → Manually verify a match
     
POST /api/v1/external-feeds/reports/{report_id}/dispute
     → Flag as questionable/false positive
     
GET  /api/v1/external-feeds/stats/coverage
     → System-wide statistics
     
GET  /api/v1/external-feeds/stats/credibility
     → Attention distribution across cases
```

---

## Data Models (Key Dataclasses)

### SourceMetadata
```python
source_id: str
name: str
organization_type: OrganizationType  # MEDIA|NGO|GOVERNMENT|RESEARCH|LEGAL_WATCHDOG
credibility_score: float  # 0-1
verification_status: VerificationStatus  # VERIFIED|PROVISIONAL|UNVERIFIED
geographic_scope: List[str]
quality_metrics: {false_positive_rate, duplicate_rate, accuracy_score}
```

### MatchCandidate
```python
article_id, case_id: str
strategy: MatchingStrategy  # Which method matched
confidence_score: float  # 0-1
strategy_scores: Dict  # Score breakdown
evidence: List[str]  # Why it matched
is_verified: bool
```

### ExternalReport
```python
report_id, case_id, source_id: str
title, url, summary: str
publication_date: datetime
match_confidence: float  # Algorithm confidence
credibility_score: float  # Source credibility
relevance_level: str  # PRIMARY|CONTEXTUAL|RELATED|MINIMAL
verification_status: str  # AUTO_MATCHED|VERIFIED|DISPUTED|REJECTED
verified_by: Optional[str]
```

### ArticleSummary
```python
article_id: str
summary_text: str
summary_type: str  # extraction|abstractive|hybrid
neutrality_score: str  # HIGHLY_NEUTRAL|NEUTRAL|SLIGHTLY_BIASED|BIASED
contains_opinion: bool
contains_defamatory_language: bool
key_facts: List[str]
parties_mentioned: List[str]
dates_mentioned: List[str]
```

---

## Testing Commands

```bash
# Run all tests
pytest tests/test_external_feeds.py -v

# Run specific test class
pytest tests/test_external_feeds.py::TestSourceRegistry -v

# Run with coverage
pytest tests/test_external_feeds.py --cov=app.external_feeds

# Run integration tests only
pytest tests/test_external_feeds.py::TestExternalFeedsIntegration -v

# Run with detailed output
pytest tests/test_external_feeds.py -vv -s
```

---

## Deployment Checklist

- [ ] Copy 9 modules to `app/external_feeds/`
- [ ] Copy tests to `tests/test_external_feeds.py`
- [ ] Copy docs to `docs/`
- [ ] Install dependencies: `pip install fastapi pydantic feedparser requests`
- [ ] Run tests: `pytest tests/test_external_feeds.py -v`
- [ ] Initialize SourceRegistry with 10 sources
- [ ] Create FastAPI app integration
- [ ] Mount API router
- [ ] Configure scheduled ingestion tasks
- [ ] Set up database schema (if using ORM)
- [ ] Configure monitoring & alerts
- [ ] Deploy to production

---

## Common Operations

### Verify a Report
```python
linking_engine.verify_report(
    report_id="rpt_123_thehindu_1",
    verified_by="reviewer@judiciary.org",
    relevance_level="PRIMARY"
)
```

### Calculate Attention for Case
```python
score = credibility_model.calculate_attention_score(
    case_id="123/2024",
    matched_articles=[...],
    source_registry=source_registry
)
print(f"Attention: {score.attention_level} ({score.score:.2f})")
```

### Generate Summary
```python
summary = summarization_engine.generate_summary(
    article_id="art001",
    title="Supreme Court Hearing",
    content=article_text,
    summary_type=SummaryType.EXTRACTION
)
print(f"Neutrality: {summary.neutrality_score}")
```

### Detect Duplicates
```python
duplicates = dedup_engine.detect_duplicates(
    articles=all_articles,
    similarity_threshold=0.85
)
for group in duplicates:
    print(f"{group.duplicate_type}: {len(group.duplicate_article_ids)} duplicates")
```

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| RSS ingestion | 100 articles/sec | Network-dependent |
| Article matching | 1,000 comparisons/sec | Per strategy |
| Deduplication | 5,000 checks/sec | Similarity-based |
| Attention calculation | <100ms | Per case |
| API response | <200ms | With 20 results |

---

## Enums Reference

### OrganizationType
- `MEDIA` - News organizations
- `NGO` - Non-governmental organizations
- `GOVERNMENT` - Official/government sources
- `RESEARCH` - Research institutions
- `LEGAL_WATCHDOG` - Legal monitoring groups

### ArticleStatus
- `RAW` - Just ingested
- `NORMALIZED` - Cleaned and processed
- `PROCESSED` - Ready for matching
- `MATCHED` - Linked to case(s)
- `REJECTED` - Not relevant

### MatchingStrategy
- `CASE_NUMBER` - Explicit "123/2024"
- `PARTY_NAMES` - Plaintiff/Defendant
- `JUDGE_NAME` - Judge mentioned
- `COURT_NAME` - Court mention
- `KEYWORDS` - Fuzzy keywords
- `SIMILARITY` - Similarity-based

### NeutralityScore
- `HIGHLY_NEUTRAL` - Opinion ≤20%
- `NEUTRAL` - Balanced presentation
- `SLIGHTLY_BIASED` - Minor bias detected
- `BIASED` - Clear opinion

### AttentionLevel
- `MINIMAL` - 1-2 sources (0.0-0.2)
- `LOW` - 3-5 sources (0.2-0.4)
- `MODERATE` - 6-15 sources (0.4-0.6)
- `HIGH` - 16-50 sources (0.6-0.8)
- `VERY_HIGH` - 50+ sources (0.8-1.0)

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Low match confidence | Case not explicit | Manual verification or improve matching |
| High false positives | Unverified sources | Update quality metrics, reduce threshold |
| Duplicates not detected | High threshold | Lower similarity_threshold parameter |
| Slow API response | Large result set | Use pagination with limit parameter |
| Memory issues | Too many articles | Archive old articles, clear caches |

---

## File Locations

```
/backend/
├── app/
│   └── external_feeds/
│       ├── __init__.py
│       ├── sources.py
│       ├── ingestion.py
│       ├── entity_matching.py
│       ├── deduplication.py
│       ├── credibility.py
│       ├── linking.py
│       ├── summarization.py
│       ├── api.py
│       └── README.md
├── tests/
│   └── test_external_feeds.py
├── docs/
│   ├── EXTERNAL_FEEDS_ARCHITECTURE.md
│   └── EXTERNAL_FEEDS_USER_GUIDE.md
└── EXTERNAL_FEEDS_COMPLETION_SUMMARY.md
```

---

## Pre-loaded Sources (10)

| Source | Type | Credibility | Coverage |
|--------|------|-------------|----------|
| The Hindu | MEDIA | 0.95 | India-wide |
| The Wire | MEDIA | 0.93 | India-wide |
| Indian Express | MEDIA | 0.92 | India-wide |
| Deccan Chronicle | MEDIA | 0.88 | India-wide |
| Bar Council India | LEGAL_WATCHDOG | 0.98 | India |
| Indian Kanoon | RESEARCH | 0.96 | India |
| PRS Legislative | RESEARCH | 0.95 | India |
| Human Rights Watch | NGO | 0.94 | Global |
| Amnesty International | NGO | 0.93 | Global |
| Supreme Court of India | GOVERNMENT | 1.0 | India |

---

## Key Formulas

### Attention Score
```
score = (credible_sources × 0.35) +
        (recency × 0.25) +
        (diversity × 0.20) +
        (volume × 0.20)
```

### Similarity Score
```
similarity = (title_sim × 0.40) +
             (content_sim × 0.35) +
             (temporal_prox × 0.15) +
             (source_sim × 0.10)
```

### Credibility from Source Metrics
```
credibility = base_score
            - (false_positive_rate × 0.05)
            - (duplicate_rate × 0.03)
            + (accuracy_score × 0.02)
```

---

## Response Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | GET /sources returns list |
| 404 | Not found | Case has no coverage |
| 422 | Invalid data | Bad request format |
| 503 | Service unavailable | Component not initialized |

---

## Monitoring Metrics

```python
# Track these daily:
metrics = {
    'articles_ingested_today': int,
    'articles_matched': int,
    'match_rate': float,  # matched/total
    'false_positive_rate': float,  # rejected/auto_matched
    'verification_rate': float,  # verified/total
    'average_match_confidence': float,
    'api_error_rate': float,
    'cases_with_coverage': int,
}

# Alert if:
- verification_rate < 0.5  # Too many unverified
- false_positive_rate > 0.2  # Too many errors
- ingestion_rate < 100  # Not enough articles
- api_error_rate > 0.01  # Too many API errors
```

---

## Documentation Links

- **Architecture Guide**: `docs/EXTERNAL_FEEDS_ARCHITECTURE.md`
- **User Guide**: `docs/EXTERNAL_FEEDS_USER_GUIDE.md`
- **Module README**: `app/external_feeds/README.md`
- **Test Reference**: `tests/test_external_feeds.py`
- **Completion Summary**: `EXTERNAL_FEEDS_COMPLETION_SUMMARY.md`

---

**Last Updated:** March 18, 2026 | **Version:** 1.0.0 | **Status:** Production Ready
