"""
Test Suite for External Feeds Integration System
Comprehensive tests for sources, ingestion, matching, deduplication, credibility, linking, summarization, and API
"""

import pytest
from datetime import datetime, timedelta
from typing import List

# Import modules under test
from app.external_feeds.sources import SourceRegistry, SourceMetadata, OrganizationType, VerificationStatus
from app.external_feeds.ingestion import IngestionPipeline, RawArticle, ArticleStatus
from app.external_feeds.entity_matching import CaseMatchingEngine, MatchCandidate, MatchingStrategy
from app.external_feeds.deduplication import DeduplicationEngine
from app.external_feeds.credibility import CredibilityModel, AttentionLevel
from app.external_feeds.linking import ExternalReportLinkingEngine, ReportVerificationStatus
from app.external_feeds.summarization import SummarizationEngine, NeutralityScore, ArticleSummary


# =========================================================================
# FIXTURES
# =========================================================================

@pytest.fixture
def source_registry():
    """Initialize source registry."""
    return SourceRegistry()


@pytest.fixture
def ingestion_pipeline():
    """Initialize ingestion pipeline."""
    return IngestionPipeline()


@pytest.fixture
def matching_engine():
    """Initialize matching engine."""
    return CaseMatchingEngine()


@pytest.fixture
def dedup_engine():
    """Initialize deduplication engine."""
    return DeduplicationEngine()


@pytest.fixture
def credibility_model():
    """Initialize credibility model."""
    return CredibilityModel()


@pytest.fixture
def linking_engine():
    """Initialize linking engine."""
    return ExternalReportLinkingEngine()


@pytest.fixture
def summarization_engine():
    """Initialize summarization engine."""
    return SummarizationEngine()


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    return [
        {
            "source_id": "the_hindu",
            "source_name": "The Hindu",
            "title": "Supreme Court Orders Investigation in Case 123/2024",
            "content": "The Supreme Court of India has ordered an investigation into the case between Plaintiff vs Defendant.",
            "url": "https://thehindu.com/article1",
            "publication_date": datetime.now(),
            "confidence_score": 0.95,
        },
        {
            "source_id": "the_wire",
            "source_name": "The Wire",
            "title": "High Court Hearing: Judge Singh Presides Over Case 123/2024",
            "content": "The High Court of Delhi heard arguments in case 123/2024 with Judge Singh presiding.",
            "url": "https://thewire.in/article2",
            "publication_date": datetime.now() - timedelta(days=1),
            "confidence_score": 0.92,
        },
        {
            "source_id": "amnestyintl",
            "source_name": "Amnesty International",
            "title": "India: Justice Delayed in Landmark Case 123/2024",
            "content": "Amnesty International expresses concern about delays in case 123/2024.",
            "url": "https://amnesty.org/article3",
            "publication_date": datetime.now() - timedelta(days=2),
            "confidence_score": 0.88,
            "organization_type": "NGO",
        },
    ]


# =========================================================================
# SOURCE REGISTRY TESTS
# =========================================================================

class TestSourceRegistry:
    """Test cases for source registry."""

    def test_add_and_retrieve_source(self, source_registry):
        """Test adding and retrieving a source."""
        registry = source_registry
        
        # Get a pre-loaded source
        hindu_source = registry.get_source("the_hindu")
        assert hindu_source is not None
        assert hindu_source.name == "The Hindu"

    def test_get_credibility_score(self, source_registry):
        """Test credibility score calculation."""
        registry = source_registry
        
        score = registry.get_credibility_score("the_hindu")
        assert 0.0 <= score <= 1.0
        assert score > 0.9  # The Hindu should be highly credible

    def test_list_verified_sources(self, source_registry):
        """Test filtering verified sources."""
        registry = source_registry
        
        verified = registry.get_verified_sources()
        assert len(verified) > 0
        assert all(s.verification_status == VerificationStatus.VERIFIED for s in verified)

    def test_get_media_sources(self, source_registry):
        """Test filtering media sources."""
        registry = source_registry
        
        media = registry.get_media_sources()
        assert len(media) > 0
        assert all(s.organization_type == OrganizationType.MEDIA for s in media)

    def test_get_ngo_sources(self, source_registry):
        """Test filtering NGO sources."""
        registry = source_registry
        
        ngos = registry.get_ngo_sources()
        assert len(ngos) > 0
        assert all(s.organization_type == OrganizationType.NGO for s in ngos)

    def test_update_quality_metrics(self, source_registry):
        """Test updating quality metrics."""
        registry = source_registry
        
        success = registry.update_quality_metrics(
            "the_hindu",
            false_positive_rate=0.02,
            duplicate_rate=0.05,
            accuracy_score=0.98,
        )
        assert success

    def test_registry_statistics(self, source_registry):
        """Test getting registry statistics."""
        registry = source_registry
        
        stats = registry.get_stats()
        assert stats["total_sources"] > 0
        assert stats["active_sources"] > 0
        assert "by_organization_type" in stats
        assert "average_credibility" in stats


# =========================================================================
# INGESTION TESTS
# =========================================================================

class TestIngestionPipeline:
    """Test cases for ingestion pipeline."""

    def test_ingest_manual_article(self, ingestion_pipeline):
        """Test manual article ingestion."""
        pipeline = ingestion_pipeline
        
        result = pipeline.ingest_manual(
            source_id="test_source",
            title="Test Article",
            content="Test content about court case",
            url="https://test.com/article",
            publication_date=datetime.now(),
        )
        
        assert result is not None
        assert result.title == "Test Article"
        assert result.status == ArticleStatus.RAW

    def test_get_articles_by_source(self, ingestion_pipeline, sample_articles):
        """Test retrieving articles by source."""
        pipeline = ingestion_pipeline
        
        # Ingest articles
        for article in sample_articles:
            pipeline.ingest_manual(
                source_id=article["source_id"],
                title=article["title"],
                content=article["content"],
                url=article["url"],
                publication_date=article["publication_date"],
            )
        
        # Retrieve by source
        hindu_articles = pipeline.get_articles_by_source("the_hindu")
        assert len(hindu_articles) > 0

    def test_update_article_status(self, ingestion_pipeline):
        """Test updating article status."""
        pipeline = ingestion_pipeline
        
        article = pipeline.ingest_manual(
            source_id="test",
            title="Test",
            content="Content",
            url="https://test.com",
            publication_date=datetime.now(),
        )
        
        success = pipeline.update_article_status(
            article.article_id,
            ArticleStatus.PROCESSED,
        )
        assert success

    def test_get_ingestion_stats(self, ingestion_pipeline, sample_articles):
        """Test ingestion statistics."""
        pipeline = ingestion_pipeline
        
        # Ingest articles
        for article in sample_articles:
            pipeline.ingest_manual(
                source_id=article["source_id"],
                title=article["title"],
                content=article["content"],
                url=article["url"],
                publication_date=article["publication_date"],
            )
        
        stats = pipeline.get_ingestion_stats()
        assert stats["total_articles"] >= 3
        assert stats["by_status"]["raw"] >= 3


# =========================================================================
# ENTITY MATCHING TESTS
# =========================================================================

class TestEntityMatching:
    """Test cases for entity matching engine."""

    def test_match_by_case_number(self, matching_engine):
        """Test case number matching."""
        engine = matching_engine
        
        # Mock case database
        engine.cases = {
            "123/2024": {"case_id": "123/2024", "parties": ["Plaintiff", "Defendant"]},
        }
        
        article = {
            "article_id": "art1",
            "title": "Supreme Court Case 123/2024",
            "content": "Discussion of case 123/2024",
        }
        
        matches = engine.find_matches(article)
        
        # Should find high confidence match
        case_matches = [m for m in matches if m.strategy == MatchingStrategy.CASE_NUMBER]
        assert len(case_matches) > 0

    def test_matching_confidence_calculation(self, matching_engine):
        """Test match confidence scoring."""
        engine = matching_engine
        
        engine.cases = {
            "456/2023": {
                "case_id": "456/2023",
                "parties": ["Smith", "Johnson"],
                "judge": "Justice Patel",
            }
        }
        
        article = {
            "article_id": "art2",
            "title": "High Court: Smith vs Johnson",
            "content": "Justice Patel heard the case",
        }
        
        matches = engine.find_matches(article, min_confidence=0.4)
        
        # Should find matches with varied confidence
        assert all(0.0 <= m.confidence_score <= 1.0 for m in matches)

    def test_matching_statistics(self, matching_engine):
        """Test matching statistics."""
        engine = matching_engine
        
        stats = engine.get_matching_stats()
        assert "total_matches" in stats
        assert "by_strategy" in stats
        assert "average_confidence" in stats


# =========================================================================
# DEDUPLICATION TESTS
# =========================================================================

class TestDeduplicationEngine:
    """Test cases for deduplication engine."""

    def test_detect_exact_duplicates(self, dedup_engine):
        """Test detection of exact duplicates."""
        engine = dedup_engine
        
        article1 = RawArticle(
            source_id="source1",
            ingestion_method="MANUAL",
            ingestion_date=datetime.now(),
            title="Identical Article Title",
            publication_date=datetime.now(),
            author="John Doe",
            url="https://site1.com/article",
            summary="Identical summary text",
            full_text="Identical full text content",
            tags=["court", "case"],
            categories=["legal"],
            status=ArticleStatus.RAW,
            content_hash="abc123",
        )
        
        article2 = RawArticle(
            source_id="source2",
            ingestion_method="MANUAL",
            ingestion_date=datetime.now() + timedelta(hours=1),
            title="Identical Article Title",
            publication_date=datetime.now(),
            author="John Doe",
            url="https://site2.com/article",
            summary="Identical summary text",
            full_text="Identical full text content",
            tags=["court", "case"],
            categories=["legal"],
            status=ArticleStatus.RAW,
            content_hash="abc123",
        )
        
        articles = [article1, article2]
        duplicates = engine.detect_duplicates(articles, similarity_threshold=0.95)
        
        # Should detect exact duplicates
        exact_groups = [g for g in duplicates if g.duplicate_type == "exact"]
        assert len(exact_groups) > 0

    def test_detect_syndicated_content(self, dedup_engine):
        """Test detection of syndicated content."""
        engine = dedup_engine
        
        # Create syndicated articles (same content within 24 hours)
        now = datetime.now()
        articles = [
            RawArticle(
                source_id=f"source{i}",
                ingestion_method="RSS_FEED",
                ingestion_date=now + timedelta(hours=i),
                title=f"Syndicated Article {i}",
                publication_date=now,
                author=f"Author {i}",
                url=f"https://site{i}.com",
                summary="Same news syndicated",
                full_text="Same news syndicated to multiple outlets",
                tags=[],
                categories=["news"],
                status=ArticleStatus.RAW,
                content_hash=f"hash{i}" if i == 0 else "hash0",
            )
            for i in range(3)
        ]
        
        duplicates = engine.detect_duplicates(articles)
        syndicated = [g for g in duplicates if g.duplicate_type == "syndicated"]
        
        # Should detect syndicated content
        assert len(syndicated) > 0

    def test_deduplication_statistics(self, dedup_engine):
        """Test deduplication statistics."""
        engine = dedup_engine
        
        stats = engine.get_deduplication_stats()
        assert "total_groups" in stats
        assert "duplicate_types" in stats


# =========================================================================
# CREDIBILITY TESTS
# =========================================================================

class TestCredibilityModel:
    """Test cases for credibility model."""

    def test_calculate_attention_score(self, credibility_model, source_registry):
        """Test attention score calculation."""
        model = credibility_model
        
        articles = [
            {
                "source_id": "the_hindu",
                "source_name": "The Hindu",
                "confidence_score": 0.95,
                "publication_date": datetime.now(),
                "organization_type": "MEDIA",
            },
            {
                "source_id": "amnesty",
                "source_name": "Amnesty International",
                "confidence_score": 0.88,
                "publication_date": datetime.now() - timedelta(days=1),
                "organization_type": "NGO",
            },
        ]
        
        score = model.calculate_attention_score(
            case_id="123/2024",
            matched_articles=articles,
            source_registry=source_registry,
        )
        
        assert score.score >= 0.0 and score.score <= 1.0
        assert score.total_articles == 2
        assert score.attention_level in list(AttentionLevel)

    def test_attention_level_determination(self, credibility_model):
        """Test attention level determination."""
        model = credibility_model
        
        # High coverage case
        articles = [
            {
                "source_id": f"source{i}",
                "source_name": f"Source {i}",
                "confidence_score": 0.8,
                "publication_date": datetime.now() - timedelta(days=i),
                "organization_type": "MEDIA",
            }
            for i in range(20)
        ]
        
        score = model.calculate_attention_score(
            case_id="456/2023",
            matched_articles=articles,
        )
        
        # More articles should increase attention level
        assert score.attention_level in [
            AttentionLevel.HIGH,
            AttentionLevel.VERY_HIGH,
        ]

    def test_credibility_stats(self, credibility_model):
        """Test credibility statistics."""
        model = credibility_model
        
        stats = model.get_credibility_stats()
        assert "cases_with_coverage" in stats
        assert "average_attention_score" in stats


# =========================================================================
# LINKING TESTS
# =========================================================================

class TestExternalReportLinking:
    """Test cases for external report linking."""

    def test_create_and_link_report(self, linking_engine):
        """Test creating and linking external report."""
        engine = linking_engine
        
        report = engine.create_external_report(
            report_id="rpt001",
            case_id="123/2024",
            source_id="the_hindu",
            source_name="The Hindu",
            title="Supreme Court Case 123/2024",
            url="https://thehindu.com/article",
            publication_date=datetime.now(),
            match_confidence=0.95,
            credibility_score=0.96,
        )
        
        assert report.case_id == "123/2024"
        assert report.report_id == "rpt001"
        assert report.verification_status == ReportVerificationStatus.AUTO_MATCHED

    def test_verify_report(self, linking_engine):
        """Test report verification."""
        engine = linking_engine
        
        report = engine.create_external_report(
            report_id="rpt002",
            case_id="456/2023",
            source_id="the_wire",
            source_name="The Wire",
            title="High Court Hearing",
            url="https://thewire.in/article",
            publication_date=datetime.now(),
            match_confidence=0.92,
            credibility_score=0.93,
        )
        
        success = engine.verify_report(
            report_id="rpt002",
            verified_by="admin@judiciary.gov",
        )
        
        assert success
        verified_report = engine.get_report("rpt002")
        assert verified_report.verification_status == ReportVerificationStatus.MANUALLY_VERIFIED

    def test_get_case_reports(self, linking_engine):
        """Test retrieving case reports."""
        engine = linking_engine
        
        # Create multiple reports for same case
        for i in range(3):
            engine.create_external_report(
                report_id=f"rpt{i}",
                case_id="case123",
                source_id=f"source{i}",
                source_name=f"Source {i}",
                title=f"Report {i}",
                url=f"https://site{i}.com",
                publication_date=datetime.now(),
                match_confidence=0.9,
                credibility_score=0.85,
            )
        
        case_reports = engine.get_case_reports("case123")
        assert len(case_reports) == 3

    def test_linking_statistics(self, linking_engine):
        """Test linking statistics."""
        engine = linking_engine
        
        stats = engine.get_linking_stats()
        assert "total_reports" in stats
        assert "cases_with_reports" in stats
        assert "verification_counts" in stats


# =========================================================================
# SUMMARIZATION TESTS
# =========================================================================

class TestSummarizationEngine:
    """Test cases for summarization engine."""

    def test_generate_extraction_summary(self, summarization_engine):
        """Test extractive summary generation."""
        engine = summarization_engine
        
        content = """
        The Supreme Court of India heard arguments in case 123/2024. 
        Justice Singh presided over the hearing involving Plaintiff vs Defendant.
        The court ordered an investigation into the allegations.
        The next hearing is scheduled for next month.
        """
        
        summary = engine.generate_summary(
            article_id="art001",
            title="Supreme Court Hearing",
            content=content,
            max_length=100,
        )
        
        assert len(summary.summary_text) > 0
        assert summary.summary_type.value == "extraction"
        assert summary.summary_word_count <= 100

    def test_neutrality_assessment(self, summarization_engine):
        """Test neutrality assessment of summary."""
        engine = summarization_engine
        
        # Neutral content
        neutral_content = "The court ruled on case 123/2024. The decision was announced yesterday."
        
        summary = engine.generate_summary(
            article_id="art002",
            title="Court Decision",
            content=neutral_content,
        )
        
        assert summary.neutrality_score in [
            NeutralityScore.HIGHLY_NEUTRAL,
            NeutralityScore.NEUTRAL,
        ]

    def test_opinion_detection(self, summarization_engine):
        """Test opinion language detection."""
        engine = summarization_engine
        
        # Opinionated content
        opinion_content = "The terrible decision in case 123/2024 was wrong and unjust."
        
        summary = engine.generate_summary(
            article_id="art003",
            title="Court Decision Criticized",
            content=opinion_content,
        )
        
        assert summary.contains_opinion

    def test_key_fact_extraction(self, summarization_engine):
        """Test extraction of key facts."""
        engine = summarization_engine
        
        content = """
        The Supreme Court heard the case on January 15, 2024.
        Justice Patel headed the bench.
        The plaintiff was represented by counsel.
        The court ordered further investigation.
        """
        
        summary = engine.generate_summary(
            article_id="art004",
            title="Key Facts",
            content=content,
        )
        
        assert len(summary.key_facts) > 0
        assert len(summary.dates_mentioned) > 0

    def test_summarization_statistics(self, summarization_engine):
        """Test summarization statistics."""
        engine = summarization_engine
        
        stats = engine.get_summarization_stats()
        assert "total_summaries" in stats
        assert "average_compression_ratio" in stats


# =========================================================================
# INTEGRATION TESTS
# =========================================================================

class TestExternalFeedsIntegration:
    """Integration tests for entire external feeds system."""

    def test_end_to_end_pipeline(
        self,
        source_registry,
        ingestion_pipeline,
        matching_engine,
        dedup_engine,
        credibility_model,
        linking_engine,
        summarization_engine,
    ):
        """Test full pipeline: ingest → match → deduplicate → score → link → summarize."""
        
        # Step 1: Ingest articles
        article = ingestion_pipeline.ingest_manual(
            source_id="the_hindu",
            title="Supreme Court Case 123/2024",
            content="The Supreme Court heard case 123/2024 with Justice Singh presiding.",
            url="https://thehindu.com/article",
            publication_date=datetime.now(),
        )
        
        assert article is not None
        
        # Step 2: Create matching engine with mock case
        matching_engine.cases = {
            "123/2024": {
                "case_id": "123/2024",
                "parties": ["Plaintiff", "Defendant"],
                "judge": "Justice Singh",
            }
        }
        
        matches = matching_engine.find_matches({
            "article_id": article.article_id,
            "title": article.title,
            "content": article.full_text,
        })
        
        assert len(matches) > 0
        
        # Step 3: Deduplicate
        duplicates = dedup_engine.detect_duplicates([article])
        assert isinstance(duplicates, list)
        
        # Step 4: Calculate credibility
        articles_list = [{
            "source_id": "the_hindu",
            "source_name": "The Hindu",
            "confidence_score": 0.95,
            "publication_date": datetime.now(),
            "organization_type": "MEDIA",
        }]
        
        attention = credibility_model.calculate_attention_score(
            case_id="123/2024",
            matched_articles=articles_list,
            source_registry=source_registry,
        )
        
        assert attention.score >= 0.0
        
        # Step 5: Link to case
        report = linking_engine.create_external_report(
            report_id="rpt001",
            case_id="123/2024",
            source_id="the_hindu",
            source_name="The Hindu",
            title=article.title,
            url=article.url,
            publication_date=article.publication_date,
            match_confidence=matches[0].confidence_score,
            credibility_score=0.96,
        )
        
        assert report.case_id == "123/2024"
        
        # Step 6: Generate summary
        summary = summarization_engine.generate_summary(
            article_id=article.article_id,
            title=article.title,
            content=article.full_text,
        )
        
        assert len(summary.summary_text) > 0
        assert summary.neutrality_score in list(NeutralityScore)


# =========================================================================
# RUN TESTS
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
