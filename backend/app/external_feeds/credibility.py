"""
Credibility Model
Computes credibility scores based on media coverage and attention

Tracks external media attention for cases.
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class AttentionLevel(str, Enum):
    """Level of external media attention."""
    MINIMAL = "minimal"  # 1-2 sources
    LOW = "low"  # 3-5 sources
    MODERATE = "moderate"  # 6-15 sources
    HIGH = "high"  # 16-50 sources
    VERY_HIGH = "very_high"  # 50+ sources


@dataclass
class ExternalAttentionScore:
    """Score indicating level of media attention for a case."""
    
    case_id: str
    attention_level: AttentionLevel
    score: float  # 0.0-1.0
    
    # Component scores
    media_source_count: int
    credible_source_count: int
    credible_source_score: float  # 0.0-1.0
    coverage_recency_score: float  # 0.0-1.0 (recent = higher)
    coverage_diversity_score: float  # 0.0-1.0 (varied orgs = higher)
    coverage_volume_score: float  # 0.0-1.0 (more articles = higher)
    
    # Metrics
    total_articles: int
    avg_article_credibility: float
    most_recent_coverage_date: Optional[datetime] = None
    first_coverage_date: Optional[datetime] = None
    coverage_span_days: int = 0
    
    # Explanation
    contributing_sources: List[str] = None  # List of source names
    calculated_at: datetime = None
    
    def __post_init__(self):
        if self.contributing_sources is None:
            self.contributing_sources = []
        if self.calculated_at is None:
            self.calculated_at = datetime.now()
        
        # Compute overall score
        self._compute_overall_score()
    
    def _compute_overall_score(self):
        """Compute overall credibility score."""
        # Weighted average of component scores
        self.score = (
            self.credible_source_score * 0.35 +
            self.coverage_recency_score * 0.25 +
            self.coverage_diversity_score * 0.20 +
            self.coverage_volume_score * 0.20
        )
        
        # Determine attention level
        if self.score >= 0.8:
            self.attention_level = AttentionLevel.VERY_HIGH
        elif self.score >= 0.6:
            self.attention_level = AttentionLevel.HIGH
        elif self.score >= 0.4:
            self.attention_level = AttentionLevel.MODERATE
        elif self.score >= 0.2:
            self.attention_level = AttentionLevel.LOW
        else:
            self.attention_level = AttentionLevel.MINIMAL


class CredibilityModel:
    """Model for computing and tracking case credibility scores."""

    def __init__(self):
        """Initialize credibility model."""
        self.attention_scores: Dict[str, ExternalAttentionScore] = {}
        self.case_coverage_history: Dict[str, List[Dict]] = {}  # case_id -> coverage events

    # =========================================================================
    # MAIN CALCULATION
    # =========================================================================

    def calculate_attention_score(
        self,
        case_id: str,
        matched_articles: List[Dict],  # List of matched articles
        source_registry = None,  # Access to source credibility scores
    ) -> ExternalAttentionScore:
        """
        Calculate external attention score for case.
        
        Args:
            case_id: ID of the case
            matched_articles: Articles matched to this case
            source_registry: Registry of sources with credibility scores
        
        Returns:
            ExternalAttentionScore
        """
        
        if not matched_articles:
            # Return minimal score for case with no coverage
            return ExternalAttentionScore(
                case_id=case_id,
                attention_level=AttentionLevel.MINIMAL,
                score=0.0,
                media_source_count=0,
                credible_source_count=0,
                credible_source_score=0.0,
                coverage_recency_score=0.0,
                coverage_diversity_score=0.0,
                coverage_volume_score=0.0,
                total_articles=0,
                avg_article_credibility=0.0,
            )

        # Calculate component scores
        media_source_count, credible_source_count, credible_score = (
            self._calculate_source_score(matched_articles, source_registry)
        )
        
        recency_score = self._calculate_recency_score(matched_articles)
        
        diversity_score = self._calculate_diversity_score(matched_articles)
        
        volume_score = self._calculate_volume_score(matched_articles)
        
        # Calculate average article credibility
        avg_credibility = (
            sum(a.get("confidence_score", 0.5) for a in matched_articles) /
            len(matched_articles)
        ) if matched_articles else 0.0
        
        # Get coverage dates
        publication_dates = [
            a.get("publication_date")
            for a in matched_articles
            if a.get("publication_date")
        ]
        
        first_date = min(publication_dates) if publication_dates else None
        last_date = max(publication_dates) if publication_dates else None
        coverage_span = (last_date - first_date).days if first_date and last_date else 0
        
        # Contributing sources
        contributing_sources = list(set(
            a.get("source_name", "Unknown")
            for a in matched_articles
        ))
        
        score = ExternalAttentionScore(
            case_id=case_id,
            attention_level=AttentionLevel.MINIMAL,  # Will be set by __post_init__
            score=0.0,  # Will be calculated
            media_source_count=media_source_count,
            credible_source_count=credible_source_count,
            credible_source_score=credible_score,
            coverage_recency_score=recency_score,
            coverage_diversity_score=diversity_score,
            coverage_volume_score=volume_score,
            total_articles=len(matched_articles),
            avg_article_credibility=avg_credibility,
            most_recent_coverage_date=last_date,
            first_coverage_date=first_date,
            coverage_span_days=coverage_span,
            contributing_sources=contributing_sources,
        )
        
        self.attention_scores[case_id] = score
        return score

    # =========================================================================
    # COMPONENT SCORE CALCULATIONS
    # =========================================================================

    def _calculate_source_score(
        self,
        articles: List[Dict],
        source_registry = None,
    ) -> tuple:
        """
        Calculate accuracy of sources reporting case (0-1).
        
        Returns:
            (media_source_count, credible_source_count, credible_score)
        """
        unique_sources = set(a.get("source_id") for a in articles if a.get("source_id"))
        media_source_count = len(unique_sources)
        
        credible_count = 0
        credible_scores = []
        
        if source_registry:
            for source_id in unique_sources:
                source = source_registry.get_source(source_id)
                if source:
                    if source.verification_status.value == "verified":
                        credible_count += 1
                    
                    credibility = source_registry.get_credibility_score(source_id)
                    if credibility is not None:
                        credible_scores.append(credibility)
        else:
            # Without source registry, estimate based on article confidence
            credible_scores = [a.get("confidence_score", 0.5) for a in articles]
            credible_count = sum(1 for score in credible_scores if score >= 0.80)
        
        avg_credible_score = (
            sum(credible_scores) / len(credible_scores)
            if credible_scores else 0.5
        )
        
        return media_source_count, credible_count, avg_credible_score

    def _calculate_recency_score(self, articles: List[Dict]) -> float:
        """
        Calculate recency of coverage (0-1).
        
        More recent coverage = higher score.
        """
        if not articles:
            return 0.0
        
        publication_dates = [
            a.get("publication_date")
            for a in articles
            if a.get("publication_date")
        ]
        
        if not publication_dates:
            return 0.5  # Default if no dates
        
        most_recent = max(publication_dates)
        days_since = (datetime.now() - most_recent).days
        
        # Score based on recency
        if days_since <= 7:
            return 1.0
        elif days_since <= 30:
            return 0.8 - (days_since - 7) / 23 * 0.3
        elif days_since <= 90:
            return 0.5 - (days_since - 30) / 60 * 0.3
        elif days_since <= 365:
            return 0.2
        else:
            return 0.05

    def _calculate_diversity_score(self, articles: List[Dict]) -> float:
        """
        Calculate diversity of covering organizations (0-1).
        
        More diverse = more credible.
        """
        if not articles:
            return 0.0
        
        # Get organization types
        org_types = set()
        source_orgs = set()
        
        for article in articles:
            org_type = article.get("organization_type")
            if org_type:
                org_types.add(org_type)
            
            source_name = article.get("source_name")
            if source_name:
                source_orgs.add(source_name)
        
        # Diversity based on organization types
        org_type_diversity = len(org_types) / 5.0  # 5 possible types
        source_diversity = min(1.0, len(source_orgs) / 5.0)  # Normalize to 1.0 at 5+ sources
        
        return max(org_type_diversity, source_diversity)

    def _calculate_volume_score(self, articles: List[Dict]) -> float:
        """
        Calculate volume of coverage (0-1).
        
        More articles = higher volume score, but with diminishing returns.
        """
        article_count = len(articles)
        
        # Logarithmic scale: diminishing returns after many articles
        if article_count <= 1:
            return 0.1
        elif article_count <= 3:
            return 0.3
        elif article_count <= 5:
            return 0.5
        elif article_count <= 10:
            return 0.7
        elif article_count <= 20:
            return 0.85
        else:
            return 1.0

    # =========================================================================
    # SCORE MANAGEMENT
    # =========================================================================

    def get_attention_score(self, case_id: str) -> Optional[ExternalAttentionScore]:
        """Retrieve attention score for case."""
        return self.attention_scores.get(case_id)

    def get_high_attention_cases(self, threshold: float = 0.6) -> List[str]:
        """Get cases with attention score above threshold."""
        return [
            case_id for case_id, score in self.attention_scores.items()
            if score.score >= threshold
        ]

    def rank_cases_by_attention(self, limit: int = 50) -> List[Tuple[str, float]]:
        """Rank cases by external attention score."""
        ranked = sorted(
            self.attention_scores.items(),
            key=lambda x: x[1].score,
            reverse=True
        )
        return [(case_id, score.score) for case_id, score in ranked[:limit]]

    # =========================================================================
    # COVERAGE HISTORY
    # =========================================================================

    def record_coverage_event(
        self,
        case_id: str,
        article_id: str,
        source_name: str,
        publication_date: datetime,
        headline: str,
    ) -> bool:
        """Record coverage event for case."""
        if case_id not in self.case_coverage_history:
            self.case_coverage_history[case_id] = []
        
        event = {
            "article_id": article_id,
            "source_name": source_name,
            "publication_date": publication_date,
            "headline": headline,
            "recorded_at": datetime.now(),
        }
        
        self.case_coverage_history[case_id].append(event)
        return True

    def get_coverage_timeline(self, case_id: str) -> List[Dict]:
        """Get coverage events for case sorted by date."""
        if case_id not in self.case_coverage_history:
            return []
        
        events = self.case_coverage_history[case_id]
        return sorted(events, key=lambda e: e["publication_date"])

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_credibility_stats(self) -> Dict:
        """Get credibility model statistics."""
        all_scores = list(self.attention_scores.values())
        
        if not all_scores:
            return {
                "cases_with_coverage": 0,
                "total_articles": 0,
                "average_attention_score": 0.0,
                "by_attention_level": {},
            }
        
        attention_level_counts = {}
        for score in all_scores:
            level = score.attention_level.value
            attention_level_counts[level] = attention_level_counts.get(level, 0) + 1
        
        return {
            "cases_with_coverage": len(all_scores),
            "total_articles": sum(s.total_articles for s in all_scores),
            "average_attention_score": sum(s.score for s in all_scores) / len(all_scores),
            "by_attention_level": attention_level_counts,
            "high_attention_cases": sum(1 for s in all_scores if s.score >= 0.75),
            "media_sources_represented": sum(s.media_source_count for s in all_scores),
        }

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_attention_scores(self) -> List[Dict]:
        """Export all attention scores."""
        return [
            {
                "case_id": score.case_id,
                "score": score.score,
                "attention_level": score.attention_level.value,
                "total_articles": score.total_articles,
                "credible_sources": score.credible_source_count,
                "contributing_sources": score.contributing_sources,
                "most_recent_coverage": (
                    score.most_recent_coverage_date.isoformat()
                    if score.most_recent_coverage_date else None
                ),
            }
            for score in self.attention_scores.values()
        ]
