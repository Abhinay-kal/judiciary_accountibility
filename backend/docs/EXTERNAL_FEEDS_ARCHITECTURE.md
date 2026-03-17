"""
External Feeds Integration System - Architecture & Integration Guide

This document covers the complete external feeds system for linking media and NGO coverage to court cases.
"""

# External Feeds Integration System

## Overview

The External Feeds Integration System tracks media and NGO coverage of court cases. It enables case transparency by identifying relevant external reporting while maintaining credibility standards and preventing defamation.

**Core Features:**
- Multi-source ingestion (RSS, APIs, web scraping, manual)
- Evidence-based case-article matching with confidence scoring
- Duplicate detection for syndicated content
- Credibility assessment based on source verification and quality metrics
- Database integration for case-media linkage
- Legal-safe neutral summarization
- RESTful API for public access

**Key Principles:**
- Evidence-based: Only link articles showing clear case references
- Source-aware: Prioritize verified, credible organizations
- Non-partisan: Present all perspectives on major cases
- Legal-safe: Avoid defamatory language, respect copyright
- Transparent: Clear confidence scores and verification status

---

## Module Architecture

### 1. Sources Module (`sources.py`)

**Purpose:** Registry and credibility model for external sources

**Key Concepts:**
- Organization types: MEDIA, NGO, GOVERNMENT, RESEARCH, LEGAL_WATCHDOG
- Verification status: VERIFIED, PROVISIONAL, UNVERIFIED
- Credibility scoring: Composite 0-1 scale based on verification + quality metrics

**Data Model:**
```python
SourceMetadata:
  - source_id: Unique identifier
  - name: Source name
  - organization_type: OrganizationType enum
  - credibility_score: 0-1 (static base credibility)
  - verification_status: VerificationStatus enum
  - geographic_scope: List of countries/regions covered
  - quality_metrics:
    - false_positive_rate: % of matched articles that aren't relevant
    - duplicate_rate: % of syndicated/duplicate content
    - accuracy_score: Percentage of correct matches verified
```

**Pre-loaded Sources (10):**
- **Media (4):** The Hindu (0.95), The Wire (0.93), Indian Express (0.92), Deccan Chronicle (0.88)
- **Legal (3):** Bar Council India (0.98), Indian Kanoon (0.96), PRS Legislative (0.95)
- **NGOs (2):** Human Rights Watch (0.94), Amnesty International (0.93)
- **Government (1):** Supreme Court of India (1.0)

**Key Methods:**
- `get_credibility_score(source_id)` - Composite score (0-1)
- `get_verified_sources()` - Filter verified only
- `update_quality_metrics()` - Update false positive/duplicate rates
- `record_ingestion()` - Track successful ingestions

**Integration Points:**
- Used by: Ingestion, Entity Matching, Credibility Model
- Provides: Source validation, credibility baseline

---

### 2. Ingestion Module (`ingestion.py`)

**Purpose:** Collect articles from multiple sources

**Ingestion Methods:**
1. **RSS Feeds:** Parse feed.xml from news sites (feedparser library)
2. **REST APIs:** Generic API ingestion with flexible response parsing
3. **Web Scraping:** Future extension support
4. **Manual Submission:** Single article manual input
5. **Direct Submission:** Programmatic article insertion

**Data Model:**
```python
RawArticle:
  - source_id: Source identifier
  - ingestion_method: RSS_FEED | API | WEB_SCRAPE | MANUAL | DIRECT
  - title, author, url, summary, full_text
  - publication_date: When article published
  - tags, categories: Article classification
  - content_hash: SHA256 hash of content (for deduplication)
  - status: RAW → NORMALIZED → PROCESSED → MATCHED → REJECTED
  - language: Detected language
  - processing_notes: Error tracking
```

**Key Methods:**
- `ingest_rss_feed(source_id, feed_url)` - Parse RSS
- `ingest_from_api(source_id, endpoint, params)` - Get from API
- `ingest_manual(...)` - Single article ingestion
- `get_articles_by_source(source_id)` - Retrieve articles
- `update_article_status()` - Track processing
- `get_ingestion_stats()` - Statistics

**Data Cleaning:**
- HTML tag removal
- Entity decoding (&nbsp; → space, &quot; → ")
- Whitespace normalization
- URL stripping from content

**Output Quality:**
- All articles SHA256 hashed for deduplication
- Language detection for multi-language support
- Normalized text (lowercase, trimmed)

**Integration Points:**
- Input from: RSS feeds, APIs, manual
- Output to: Entity Matching, Deduplication
- Provides: Raw article data

---

### 3. Entity Matching Module (`entity_matching.py`)

**Purpose:** Link articles to court cases

**Matching Strategies (6 in priority order):**

1. **Case Number Matching** (0.98 confidence)
   - Pattern: `123/2024` or `123-2024`
   - Rule: Exact format match
   - Use: Highest confidence

2. **Party Name Matching** (0.85 confidence)
   - Pattern: `Plaintiff v. Defendant`
   - Rule: Fuzzy match of party names
   - Use: When names appear in article

3. **Judge Name Matching** (0.75 confidence)
   - Pattern: `Justice Singh presided`
   - Rule: Judge titles + names
   - Use: Additional evidence

4. **Court Name Matching** (0.45 confidence)
   - Warning: Lower confidence (multiple cases per court)
   - Pattern: `Supreme Court heard`, `High Court of Delhi`
   - Use: Context only

5. **Keyword + Temporal Matching** (0.80 max confidence)
   - Pattern: Keywords in article + publication date near case date
   - Bonus: Recent articles get temporal proximity boost
   - Use: When other methods uncertain

6. **Fuzzy Matching** (0.70 max confidence)
   - Pattern: Similarity across title + content
   - Factors: Title (40%), content (35%), temporal (15%), source (10%)
   - Use: Last resort

**Confidence Calculation:**
- Each strategy yields 0-1 score
- Strategies run independently
- Highest confidence for article-case pair returned
- Duplicates removed (one match per article-case)

**Data Model:**
```python
MatchCandidate:
  - article_id, case_id: What matched
  - strategy: Which method found it
  - confidence_score: 0-1 overall
  - strategy_scores: Dict of individual strategy scores
  - evidence: List of matching factors found
  - is_verified: Manual verification status
```

**Key Methods:**
- `find_matches(article, min_confidence=0.60)` - Main endpoint
- `_match_by_case_number()` - Strategy 1
- `_match_by_party_names()` - Strategy 2
- `_match_by_judge_name()` - Strategy 3
- `_match_by_court_name()` - Strategy 4
- `_match_by_keywords()` - Strategy 5
- `verify_match()` - Manual verification
- `get_matching_stats()` - Statistics

**Integration Points:**
- Input from: Ingestion Pipeline
- Output to: Deduplication, Credibility Model
- Provides: Article-case linkage with confidence

---

### 4. Deduplication Module (`deduplication.py`)

**Purpose:** Detect and manage duplicate articles

**Duplicate Types (4 classifications):**

1. **Exact Duplicates** (similarity ≥ 0.95)
   - Same content word-for-word
   - Action: Archive or merge
   - Example: Same press release from multiple outlets

2. **Syndicated Content** (same timeframe, slight variation)
   - Same news syndicated across outlets (within 24 hours)
   - Indicators: Different headlines but nearly identical content
   - Action: Keep primary, mark others as syndications

3. **Paraphrased** (similarity 0.75-0.95)
   - Same story rewritten in different words
   - Indicators: Similar structure, different phrasing
   - Action: Flag for manual review

4. **Near Duplicates** (similarity 0.60-0.75)
   - Similar but not clearly duplicate
   - Indicators: Shared facts/parties but different angles
   - Action: Keep separate but flag relationship

**Similarity Metrics:**
- Title similarity: 40% weight
- Content similarity: 35% weight (using difflib)
- Temporal proximity: 15% weight (same day = higher)
- Source similarity: 10% weight (same org = higher)

**Time Window Logic:**
- Syndication detected within 24-hour window
- Window configurable per source

**Data Model:**
```python
DuplicateGroup:
  - group_id: SHA256 hash of group
  - primary_article_id: Article kept (others archived)
  - duplicate_article_ids: [Other articles in group]
  - similarity_scores: Dict of pairwise scores
  - duplicate_type: exact | syndicated | paraphrased | near_duplicate
  - detection_timestamp: When detected
```

**Key Methods:**
- `detect_duplicates(articles, threshold=0.85)` - Main endpoint
- `_compute_similarity()` - Multi-metric scoring
- `mark_primary()` - Select article to keep
- `consolidate_duplicates()` - Archive/merge/delete action
- `get_deduplicated_articles()` - Return non-duplicates only
- `detect_syndicated_content()` - Find syndication patterns
- `get_deduplication_stats()` - Statistics

**Deduplication Output:**
- Reduces noise in case coverage
- Avoids counting same news twice
- Maintains coverage diversity

**Integration Points:**
- Input from: Entity Matching
- Output to: Credibility Model, Linking
- Provides: De-duped article list

---

### 5. Credibility Module (`credibility.py`)

**Purpose:** Score media attention for cases

**Attention Score Components** (0-1 scale):

1. **Source Credibility Score** (35% weight)
   - Base: SourceRegistry.get_credibility_score()
   - Penalty: -5% per false positive
   - Penalty: -3% per duplicate in this source
   - Bonus: +2% if article verified manually

2. **Coverage Recency Score** (25% weight)
   - Within 7 days: 1.0
   - 8-30 days: Linear decay to 0.5
   - 31-90 days: 0.5 to 0.2
   - 91+ days: 0.2 to 0.05

3. **Coverage Diversity Score** (20% weight)
   - Variety of organization types (MEDIA, NGO, GOVERNMENT, etc.)
   - More types = higher score
   - Maximum: 5 types = 1.0

4. **Coverage Volume Score** (20% weight)
   - Logarithmic scale (diminishing returns)
   - 1 article: 0.1
   - 3 articles: 0.3
   - 5 articles: 0.5
   - 10 articles: 0.7
   - 20+ articles: 1.0

**Overall Attention Score:**
```
score = (credible × 0.35) + (recency × 0.25) + (diversity × 0.20) + (volume × 0.20)
```

**Attention Levels** (semantic bucketing of 0-1 score):
- MINIMAL: 0.0-0.2 (1-2 sources, low attention)
- LOW: 0.2-0.4 (3-5 sources)
- MODERATE: 0.4-0.6 (6-15 sources)
- HIGH: 0.6-0.8 (16-50 sources)
- VERY_HIGH: 0.8-1.0 (50+ sources, sustained coverage)

**Data Model:**
```python
ExternalAttentionScore:
  - case_id, score (0-1), attention_level
  - media_source_count: Total distinct sources
  - credible_source_count: Verified sources
  - total_articles: Ingested articles
  - avg_article_credibility: Mean confidence
  - coverage_span_days: First to last article
  - contributing_sources: List of source names
  - calculated_at: Timestamp
```

**Key Methods:**
- `calculate_attention_score()` - Main calculation
- `get_attention_score()` - Retrieve cached score
- `get_high_attention_cases()` - Filter by threshold
- `rank_cases_by_attention()` - Top N cases
- `record_coverage_event()` - Track individual articles
- `get_coverage_timeline()` - Historical articles for case
- `get_credibility_stats()` - System statistics

**Usage Patterns:**
- Transparency indicator: How widely covered
- Risk indicator: High coverage = more scrutiny
- Verification signal: Multiple sources = higher confidence

**Integration Points:**
- Input from: Deduplication, SourceRegistry
- Output to: Linking, API
- Provides: Attention score for cases

---

### 6. Linking Module (`linking.py`)

**Purpose:** Link external articles to cases in database

**Report Verification Workflow:**

1. **Auto-Matched** (Initial state)
   - Algorithm matched article to case
   - Confidence score 0-1
   - Requires manual review

2. **Manually Verified** (Best state)
   - Human reviewer confirmed match
   - Verified by: User ID
   - Timestamp: Verification date
   - Bonus: Increases case credibility

3. **Disputed** (Under review)
   - Match is questionable
   - May be false positive
   - Requires investigation

4. **Rejected** (Final state)
   - Confirmed false positive
   - Don't show in case coverage
   - Update source's false positive rate

**Relevance Levels** (semantic classification):
- PRIMARY: Core case coverage (direct reporting)
- CONTEXTUAL: Background/history (provides context)
- RELATED: Related but not direct
- MINIMAL: Tangential (barely relevant)

**Data Model:**
```python
ExternalReport:
  - report_id: Unique identifier
  - case_id: Which case
  - source_id, source_name: Which source
  - title, url: Article metadata
  - publication_date: When published
  - match_confidence: Algorithm confidence (0-1)
  - credibility_score: Source credibility
  - relevance_level: PRIMARY | CONTEXTUAL | RELATED | MINIMAL
  - verification_status: AUTO_MATCHED | MANUALLY_VERIFIED | DISPUTED | REJECTED
  - verified_by: User who verified
  - verification_timestamp: When verified
```

**Key Methods:**
- `create_external_report()` - Create and link article
- `get_report()` - Retrieve single report
- `get_case_reports()` - All articles for case
- `verify_report()` - Manual verification
- `dispute_report()` - Flag as questionable
- `reject_report()` - Mark as false positive
- `link_multiple_reports()` - Batch linking
- `get_case_report_summary()` - Statistics for case
- `get_linking_stats()` - System statistics
- `export_reports()` - Data export

**Database Schema** (when using ORM):
```sql
CREATE TABLE external_reports (
  report_id VARCHAR PRIMARY KEY,
  case_id VARCHAR,
  source_id VARCHAR,
  source_name VARCHAR,
  title VARCHAR,
  url VARCHAR,
  publication_date DATETIME,
  match_confidence FLOAT,
  credibility_score FLOAT,
  relevance_level VARCHAR,
  verification_status VARCHAR,
  verified_by VARCHAR,
  verification_timestamp DATETIME,
  summary TEXT,
  full_text TEXT,
  ingestion_timestamp DATETIME,
  
  FOREIGN KEY (case_id) REFERENCES cases(case_id),
  INDEX idx_case_id,
  INDEX idx_source_id,
  INDEX idx_verification_status
);
```

**Integration Points:**
- Input from: Credibility Model (with scores), Matching Engine (with confidence)
- Output to: API, Summarization
- Provides: Case-article linkage records

---

### 7. Summarization Module (`summarization.py`)

**Purpose:** Generate legal-safe, neutral summaries

**Neutrality Assessment:**

Opinion indicators penalize summaries containing:
- Allegedly, reportedly, claims
- Should, must, ought
- Good/bad, excellent/terrible
- Seems, appears to be, suggests

Defamatory language penalties for:
- Fraud, corruption, abuse
- Guilty, innocent (before verdict)
- Criminal language without context

**Neutrality Levels** (assessed automatically):
- HIGHLY_NEUTRAL: Opinion ≤20%, defamatory ≤10%
- NEUTRAL: Opinion ≤40%, defamatory ≤20%
- SLIGHTLY_BIASED: Opinion ≤60%
- BIASED: Opinion >60%

**Summary Types:**

1. **Extraction** (Sentences from article)
   - Select best sentences (position, informativeness)
   - Preserve original wording
   - Fast, reliable
   - Best for: News articles (factual)

2. **Abstractive** (Rewritten summary)
   - Reword content in neutral tone
   - Remove opinion language
   - Requires NLP model
   - Best for: Opinionated articles, opinion columns

3. **Hybrid** (Both methods combined)
   - Extract key facts
   - Rewrite for neutrality
   - Balanced approach
   - Best for: General use

**Key Facts Extraction:**
- Case numbers (123/2024 pattern)
- Party names (Plaintiff v. Defendant)
- Judge names (Justice Singh)
- Court names (Supreme Court, High Court)
- Dates (January 15, 2024)
- Specific decisions/orders

**Data Model:**
```python
ArticleSummary:
  - article_id: Which article
  - summary_text: Generated summary
  - summary_type: extraction | abstractive | hybrid
  - source_word_count: Original length
  - summary_word_count: Summary length
  - compression_ratio: Summary/Original
  - neutrality_score: HIGHLY_NEUTRAL | NEUTRAL | SLIGHTLY_BIASED | BIASED
  - contains_opinion: Boolean
  - contains_defamatory_language: Boolean
  - copyright_safe: Boolean
  - key_facts: List of sentences
  - parties_mentioned: List of parties
  - defendants_mentioned: List
  - courts_mentioned: List
  - dates_mentioned: List
```

**Key Methods:**
- `generate_summary()` - Main endpoint
- `_extract_summary()` - Extraction strategy
- `_abstractive_summary()` - Rewriting strategy
- `_hybrid_summary()` - Combined
- `_detect_opinion_language()` - Neutrality check
- `_detect_defamatory_language()` - Safety check
- `_extract_key_facts()` - Fact extraction
- `get_neutral_summaries()` - Filter by neutrality
- `get_summarization_stats()` - Statistics

**Quality Assurance:**
- No quote duplication
- Copyright-safe (not just copying)
- Legal language reviewed
- Names anonymized where appropriate
- Opinion language flagged or removed

**Integration Points:**
- Input from: Linking (full article text)
- Output to: API display
- Provides: User-friendly summary

---

### 8. API Module (`api.py`)

**Purpose:** RESTful access to external feeds

**Base Path:** `/api/v1/external-feeds`

**Endpoints:**

#### Sources (`/sources`)
```
GET /sources
  Query: organization_type, verified_only, limit, offset
  Response: List[SourceResponse] with credibility scores
  
GET /sources/{source_id}
  Response: Single SourceResponse with stats
```

#### Case Media (`/cases/{case_id}`)
```
GET /cases/{case_id}/media
  Query: verified_only, limit, offset
  Response: CaseMediaResponse with articles + attention score
  
GET /cases/{case_id}/media/summary
  Response: Summary stats for case coverage
  
GET /cases/{case_id}/attention-score
  Response: ExternalAttentionScore with breakdown
```

#### Reports (`/reports`)
```
GET /reports/{report_id}
  Response: ExternalReportResponse with metadata
  
GET /reports/{report_id}/summary
  Response: ExternalReportDetailResponse with generated summary
  
POST /reports/{report_id}/verify
  Body: {verified_by, relevance_level, notes}
  Response: Verification confirmation
  
POST /reports/{report_id}/dispute
  Response: Dispute confirmation
```

#### Statistics (`/stats`)
```
GET /stats/coverage
  Response: System-wide coverage statistics
  
GET /stats/credibility
  Response: Attention score distribution
```

**Response Models:**

```python
SourceResponse:
  - source_id, name, organization_type
  - credibility_score, verification_status
  - geographic_scope, language

ExternalReportResponse:
  - report_id, case_id
  - source_id, source_name
  - title, url, publication_date
  - match_confidence, credibility_score
  - relevance_level, verification_status
  - summary

CaseMediaResponse:
  - case_id
  - total_reports, verified_reports
  - external_attention_score, attention_level
  - sources (list)
  - date_range
  - average_confidence, average_credibility
  - reports (list of ExternalReportResponse)
```

**Error Handling:**
- 404: Resource not found
- 503: Service unavailable (backend not configured)
- 422: Invalid request data

**Authentication:** (Optional future enhancement)
- API key for write operations
- Public read access for transparency

**Rate Limiting:** (Optional future enhancement)
- 100 req/min per IP
- 1000 req/day per API key

**Integration Points:**
- Consumes: All other modules (source_registry, engines)
- Output to: Public/internal users
- Provides: JSON APIs for integration

---

## Integration Examples

### Example 1: New Case Coverage Detection

```python
# 1. Ingest daily RSS feeds
articles = pipeline.ingest_rss_feed(
    "the_hindu",
    "https://thehindu.com/feed"
)

# 2. Find matching cases
for article in articles:
    matches = matching_engine.find_matches(article, min_confidence=0.70)
    for match in matches:
        # 3. Check for duplicates
        duplicates = dedup_engine.detect_duplicates([article])
        if duplicates[0].duplicate_type == "exact":
            continue  # Skip exact duplicates
        
        # 4. Calculate case attention
        attention = credibility_model.calculate_attention_score(
            case_id=match.case_id,
            matched_articles=[...],
            source_registry=source_registry
        )
        
        # 5. Link to case
        report = linking_engine.create_external_report(
            report_id=f"rpt_{match.case_id}_{article.source_id}",
            case_id=match.case_id,
            source_id=article.source_id,
            source_name=source_registry.get_source(article.source_id).name,
            title=article.title,
            url=article.url,
            publication_date=article.publication_date,
            match_confidence=match.confidence_score,
            credibility_score=source_registry.get_credibility_score(article.source_id),
        )
        
        # 6. Generate summary
        summary = summarization_engine.generate_summary(
            article_id=article.article_id,
            title=article.title,
            content=article.full_text,
        )
        
        print(f"Case {match.case_id}: {article.title}")
        print(f"  Confidence: {match.confidence_score}")
        print(f"  Attention: {attention.attention_level}")
        print(f"  Summary: {summary.summary_text[:100]}...")
```

### Example 2: API Usage for Case Details

```python
# Client code to view external coverage of case
import requests

# Get case media coverage
response = requests.get(
    "https://judiciary-api.gov.in/api/v1/external-feeds/cases/123/2024/media",
    params={"verified_only": True, "limit": 10}
)

case_media = response.json()

print(f"Case: {case_media['case_id']}")
print(f"External Coverage: {case_media['total_reports']} articles")
print(f"Attention Score: {case_media['external_attention_score']:.2f}")
print(f"Coverage Sources: {', '.join(case_media['sources'])}")
print(f"\nArticles:")
for report in case_media['reports']:
    print(f"  - {report['title']}")
    print(f"    Source: {report['source_name']}")
    print(f"    Confidence: {report['match_confidence']:.2f}")
    print(f"    {report['summary'][:80]}...")
```

### Example 3: Verification Workflow

```python
# Reviewer verifies auto-matched reports
reports = linking_engine.get_case_reports(
    "456/2023",
    verification_status=ReportVerificationStatus.AUTO_MATCHED
)

for report in reports:
    print(f"Review: {report.title}")
    print(f"  From: {report.source_name}")
    print(f"  Confidence: {report.match_confidence}")
    
    if report.match_confidence < 0.70 or should_dispute(report):
        linking_engine.dispute_report(report.report_id)
        print("  → Marked as disputed")
    else:
        linking_engine.verify_report(
            report_id=report.report_id,
            verified_by="reviewer@judiciary.gov",
            relevance_level=ReportRelevanceLevel.PRIMARY
        )
        print("  ✓ Verified")
```

---

## Deployment & Operations

### Configuration

```python
# Initialize all components
source_registry = SourceRegistry()
ingestion = IngestionPipeline()
matching = CaseMatchingEngine(case_database=db)
dedup = DeduplicationEngine()
credibility = CredibilityModel()
linking = ExternalReportLinkingEngine()
summarization = SummarizationEngine()

# Create API router
api = ExternalFeedsAPIRouter(
    source_registry=source_registry,
    ingestion_pipeline=ingestion,
    matching_engine=matching,
    dedup_engine=dedup,
    credibility_model=credibility,
    linking_engine=linking,
    summarization_engine=summarization,
)

# Mount to FastAPI app
app.include_router(api.get_router())
```

### Scheduled Tasks

```python
# Daily ingestion task (via Celery)
@app.task(schedule=crontab(hour=0, minute=0))
def daily_ingestion():
    """Ingest new articles from all sources daily."""
    for source in source_registry.get_verified_sources():
        if source.organization_type == OrganizationType.MEDIA:
            articles = ingestion.ingest_rss_feed(
                source.source_id,
                source.feed_url
            )

# Weekly deduplication (via Celery)
@app.task(schedule=crontab(day_of_week=0, hour=2, minute=0))
def weekly_deduplication():
    """Detect duplicates in week's articles."""
    articles = ingestion.get_articles_by_status(ArticleStatus.RAW)
    duplicates = dedup.detect_duplicates(articles)
    
    for group in duplicates:
        if group.duplicate_type in ["exact", "syndicated"]:
            dedup.consolidate_duplicates(
                group.group_id,
                keep_article_id=group.primary_article_id,
                action="archive"
            )

# Monthly review task (manual)
def monthly_review():
    """Review disputed reports and quality metrics."""
    stats = linking_engine.get_linking_stats()
    
    # Calculate false positive rate per source
    for source_id in stats['sources_represented']:
        reports = linking_engine.get_source_reports(source_id)
        disputed = sum(1 for r in reports if r.verification_status == ReportVerificationStatus.DISPUTED)
        rejected = sum(1 for r in reports if r.verification_status == ReportVerificationStatus.REJECTED)
        
        false_positive_rate = (disputed + rejected) / len(reports) if reports else 0
        
        # Update source metrics
        source_registry.update_quality_metrics(
            source_id,
            false_positive_rate=false_positive_rate
        )
```

### Monitoring

```python
# Key metrics to track
metrics = {
    "cases_with_coverage": credibility.get_credibility_stats()["cases_with_coverage"],
    "total_articles": linking_engine.get_linking_stats()["total_reports"],
    "average_attention": credibility.get_credibility_stats()["average_attention_score"],
    "verification_rate": (
        linking_engine.get_linking_stats()["verification_counts"]["manually_verified"] /
        linking_engine.get_linking_stats()["total_reports"]
    ),
    "average_confidence": linking_engine.get_linking_stats()["average_confidence"],
}

# Alert on low verification rate
if metrics["verification_rate"] < 0.5:
    alert("Low verification rate - manual review needed")

# Alert on high false positive rate
for source in source_registry.get_all_sources():
    rate = source.quality_metrics.get("false_positive_rate", 0)
    if rate > 0.2:
        alert(f"High false positive rate for {source.name}: {rate:.1%}")
```

---

## Best Practices

### For Operators

1. **Daily Ingestion**: Schedule automated ingestion from RSS feeds during off-peak hours
2. **Manual Verification**: Assign 1-2 hours daily for reviewing auto-matched reports
3. **Source Quality**: Monthly review of false positive rates and quality metrics
4. **Database Maintenance**: Weekly cleanup of old articles (>6 months) per retention policy
5. **Alert Monitoring**: Set up alerts for:
   - Low verification rates (<50%)
   - High false positive rates (>20%)
   - API errors (>1% error rate)
   - Ingestion failures (>5% failure rate)

### For Users

1. **Verify Before Citing**: Check verification status (green checkmark = manually verified)
2. **Review Confidence Scores**: Higher scores = more reliable matching
3. **Check Source Credibility**: Credibility scores shown for each source
4. **Read Generated Summary**: Summaries are neutral and fact-based
5. **Cross-Reference**: Use multiple sources for important cases
6. **Report Errors**: Flag suspected false positives for review

### For Developers

1. **Test Integrations**: Test matching algorithm with new case formats
2. **Monitor Performance**: Track query latency for API endpoints
3. **Validate Data**: Ensure all articles have required fields before ingestion
4. **Archive Old Data**: Remove duplicate articles and old articles regularly
5. **Update Sources**: Add new sources as they become available
6. **Document Cases**: Keep documentation of special case formats

---

## Security & Privacy

### Data Protection
- All URLs are HTTPS only
- No personal information stored from articles
- Summaries don't include sensitive data
- Source credibility is public knowledge

### Legal Safety
- Defamatory language detection prevents reputational harm
- Neutrality assessment ensures fair presentation
- Opinion language flagged in summaries
- Verification workflow prevents false matches

### Access Control
- Public API for case media information
- Internal API for verification and administration
- Rate limiting prevents abuse
- All API calls logged for audit

---

## Limitations & Future Enhancements

### Current Limitations
- Summarization uses extraction/simple rewriting (no advanced NLP)
- Matching relies on text patterns (no deep semantic understanding)
- Deduplication is similarity-based (not AI-driven)
- Coverage limited to configured sources

### Future Enhancements
1. **Machine Learning**: Train custom models for entity extraction and case recognition
2. **Multi-Language**: Support for regional language coverage (Hindi, Tamil, etc.)
3. **Real-time Ingestion**: WebSub/PubSubHubbub support for instant updates
4. **Social Media**: Track social media mentions, discussions, public opinion
5. **Advanced NLP**: Fine-tuned language model for neutral summarization
6. **Visualization**: Coverage timeline, sentiment analysis, trend detection
7. **Collaboration**: Community annotation and expert verification
8. **Integration**: Connect to case management system for automatic linking

---

## References

### Standards
- RSS 2.0 Specification: https://www.rssboard.org/rss-specification
- RFC 4648: Base Encoding Data Formats (for URL-safe encoding)
- JSON Schema: https://json-schema.org/

### Best Practices
- W3C: Web Content Accessibility Guidelines (WCAG 2.1)
- NIST: Guidelines for Cybersecurity

### Tools
- feedparser: RSS/Atom parsing library
- requests: HTTP library for API calls
- FastAPI: Web framework
- SQLAlchemy: ORM for database

---

## Support & Contact

For questions or issues:
- Technical: github.com/judiciary-accountability/external-feeds/issues
- Feedback: feedback@judiciary-accountability.org
- Coverage Requests: coverage@judiciary-accountability.org

---

**Last Updated:** March 18, 2026
**Version:** 1.0.0
**Status:** Production
