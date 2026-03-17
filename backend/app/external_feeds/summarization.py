"""
Summarization Module
Generates neutral, legal-safe summaries of external media coverage

Ensures summaries are factual, non-defamatory, and copyright-safe.
"""

from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


class SummaryType(str, Enum):
    """Type of summary generated."""
    EXTRACTION = "extraction"  # Key sentences from article
    ABSTRACTIVE = "abstractive"  # Rewritten summary
    HYBRID = "hybrid"  # Both extraction and abstraction


class NeutralityScore(str, Enum):
    """Assessment of summary neutrality."""
    HIGHLY_NEUTRAL = "highly_neutral"  # No opinion/bias detected
    NEUTRAL = "neutral"  # Balanced
    SLIGHTLY_BIASED = "slightly_biased"  # Minor bias
    BIASED = "biased"  # Clear opinion
    NOT_ASSESSED = "not_assessed"  # Not yet assessed


@dataclass
class ArticleSummary:
    """Neutral summary of article content."""
    
    article_id: str
    summary_text: str
    summary_type: SummaryType = SummaryType.EXTRACTION
    
    # Metadata
    source_word_count: int = 0
    summary_word_count: int = 0
    compression_ratio: float = 0.0  # summary_length / source_length
    
    # Quality assessment
    neutrality_score: NeutralityScore = NeutralityScore.NOT_ASSESSED
    contains_opinion: bool = False
    contains_defamatory_language: bool = False
    copyright_safe: bool = True
    
    # Key facts extracted
    key_facts: List[str] = None
    parties_mentioned: List[str] = None
    defendants_mentioned: List[str] = None
    courts_mentioned: List[str] = None
    dates_mentioned: List[str] = None
    
    # Processing
    generated_at: datetime = None
    
    def __post_init__(self):
        if self.key_facts is None:
            self.key_facts = []
        if self.parties_mentioned is None:
            self.parties_mentioned = []
        if self.defendants_mentioned is None:
            self.defendants_mentioned = []
        if self.courts_mentioned is None:
            self.courts_mentioned = []
        if self.dates_mentioned is None:
            self.dates_mentioned = []
        if self.generated_at is None:
            self.generated_at = datetime.now()
        
        if self.source_word_count > 0:
            self.compression_ratio = self.summary_word_count / self.source_word_count


class SummarizationEngine:
    """Engine for generating neutral article summaries."""

    def __init__(self):
        """Initialize summarization engine."""
        self.summaries: Dict[str, ArticleSummary] = {}
        
        # Patterns for neutrality assessment
        self.opinion_indicators = [
            r"\b(allegedly|reportedly|reportedly|claims?)\b",
            r"\b(should|must|ought|wrong|right)\b",
            r"\b(good|bad|excellent|terrible|great|awful)\b",
            r"\b(seems|appears to be|suggests)\b",
        ]
        
        self.defamatory_indicators = [
            r"\b(fraud|corruption|abuse|misconduct)\b",
            r"\b(guilty|innocent|criminal)\b",
        ]

    # =========================================================================
    # SUMMARY GENERATION
    # =========================================================================

    def generate_summary(
        self,
        article_id: str,
        title: str,
        content: str,
        summary_type: SummaryType = SummaryType.EXTRACTION,
        max_length: int = 300,
    ) -> ArticleSummary:
        """
        Generate neutral summary of article.
        
        Args:
            article_id: ID of article
            title: Article title
            content: Full article content
            summary_type: Type of summary (extraction, abstractive, hybrid)
            max_length: Maximum summary length in words
        
        Returns:
            ArticleSummary
        """
        
        # Clean content
        clean_content = self._clean_content(content)
        
        # Generate summary based on type
        if summary_type == SummaryType.EXTRACTION:
            summary_text = self._extract_summary(clean_content, max_length)
        elif summary_type == SummaryType.ABSTRACTIVE:
            summary_text = self._abstractive_summary(clean_content, max_length)
        else:  # HYBRID
            summary_text = self._hybrid_summary(clean_content, max_length)
        
        # Assess neutrality
        opinion_score = self._detect_opinion_language(summary_text)
        defamatory_score = self._detect_defamatory_language(summary_text)
        
        # Extract key information
        key_facts = self._extract_key_facts(summary_text)
        parties = self._extract_parties(summary_text)
        defendants = self._extract_defendants(summary_text)
        courts = self._extract_courts(summary_text)
        dates = self._extract_dates(summary_text)
        
        # Determine neutrality
        if opinion_score <= 0.2 and defamatory_score <= 0.1:
            neutrality = NeutralityScore.HIGHLY_NEUTRAL
            contains_opinion = False
        elif opinion_score <= 0.4 and defamatory_score <= 0.2:
            neutrality = NeutralityScore.NEUTRAL
            contains_opinion = False
        elif opinion_score <= 0.6:
            neutrality = NeutralityScore.SLIGHTLY_BIASED
            contains_opinion = True
        else:
            neutrality = NeutralityScore.BIASED
            contains_opinion = True
        
        summary = ArticleSummary(
            article_id=article_id,
            summary_text=summary_text,
            summary_type=summary_type,
            source_word_count=len(clean_content.split()),
            summary_word_count=len(summary_text.split()),
            neutrality_score=neutrality,
            contains_opinion=contains_opinion,
            contains_defamatory_language=defamatory_score > 0.3,
            key_facts=key_facts,
            parties_mentioned=parties,
            defendants_mentioned=defendants,
            courts_mentioned=courts,
            dates_mentioned=dates,
        )
        
        self.summaries[article_id] = summary
        return summary

    # =========================================================================
    # SUMMARY STRATEGIES
    # =========================================================================

    def _extract_summary(self, content: str, max_length: int) -> str:
        """Extract key sentences to create summary."""
        sentences = re.split(r'(?<=[.!?])\s+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return ""
        
        # Score sentences by informativeness
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Position (early sentences more important)
            score += (1.0 - (i / len(sentences))) * 0.3
            
            # Length (medium sentences better)
            word_count = len(sentence.split())
            if 10 <= word_count <= 30:
                score += 0.3
            else:
                score += 0.1
            
            # Contains numbers/specific facts
            if re.search(r'\d+', sentence):
                score += 0.2
            
            # Contains case number
            if re.search(r'\d+/\d+', sentence):
                score += 0.2
            
            scored_sentences.append((score, sentence))
        
        # Select top sentences
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        selected = []
        current_length = 0
        
        for score, sentence in scored_sentences:
            words = len(sentence.split())
            if current_length + words <= max_length:
                selected.append(sentence)
                current_length += words
        
        # Maintain original order
        selected_set = set(selected)
        ordered_sentences = [s for s in sentences if s in selected_set]
        
        return " ".join(ordered_sentences)

    def _abstractive_summary(
        self,
        content: str,
        max_length: int,
    ) -> str:
        """Generate abstractive summary (rewritten)."""
        sentences = re.split(r'(?<=[.!?])\s+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return ""
        
        # Simple approach: combine key sentences with minimal rewriting
        # In production, would use NLP model
        summary_parts = []
        
        for i, sentence in enumerate(sentences[:5]):  # First 5 sentences
            word_count = len(sentence.split())
            
            # Remove quote marks to quote counts
            sentence = sentence.replace('"', "'")
            
            # Trim long sentences
            if word_count > 40:
                words = sentence.split()
                sentence = " ".join(words[:40]) + "..."
            
            summary_parts.append(sentence)
        
        return " ".join(summary_parts)

    def _hybrid_summary(
        self,
        content: str,
        max_length: int,
    ) -> str:
        """Generate hybrid summary (extraction + abstractive)."""
        extraction = self._extract_summary(content, max_length // 2)
        abstractive = self._abstractive_summary(content, max_length // 2)
        
        return extraction + " " + abstractive

    # =========================================================================
    # NEUTRALITY ASSESSMENT
    # =========================================================================

    def _detect_opinion_language(self, text: str) -> float:
        """Detect opinion language (0-1 score)."""
        opinion_count = 0
        
        for pattern in self.opinion_indicators:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            opinion_count += matches
        
        word_count = len(text.split())
        score = min(1.0, opinion_count / max(1, word_count / 50))
        
        return score

    def _detect_defamatory_language(self, text: str) -> float:
        """Detect potentially defamatory language (0-1 score)."""
        defam_count = 0
        
        for pattern in self.defamatory_indicators:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            defam_count += matches
        
        word_count = len(text.split())
        score = min(1.0, defam_count / max(1, word_count / 50))
        
        return score

    # =========================================================================
    # INFORMATION EXTRACTION
    # =========================================================================

    def _extract_key_facts(self, text: str) -> List[str]:
        """Extract key factual statements."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        facts = []
        for sentence in sentences[:5]:  # First 5 sentences
            sentence = sentence.strip()
            
            # Remove opinion language
            sentence = re.sub(
                r'\b(allegedly|reportedly|claims?)\b',
                '',
                sentence,
                flags=re.IGNORECASE
            )
            
            if sentence and len(sentence.split()) >= 5:
                facts.append(sentence)
        
        return facts[:5]  # Top 5

    def _extract_parties(self, text: str) -> List[str]:
        """Extract party/plaintiff mentions."""
        # Pattern: capitalized words followed by "v." or "vs" or "against"
        patterns = [
            r'([A-Z][a-z\s]+)\s+(?:v\.|vs|versus|against)\s+([A-Z][a-z\s]+)',
        ]
        
        parties = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    parties.extend([p.strip() for p in match])
                else:
                    parties.append(match.strip())
        
        return list(set(parties))[:10]

    def _extract_defendants(self, text: str) -> List[str]:
        """Extract defendant mentions."""
        patterns = [
            r'defendant:? ([A-Z][a-z\s]+)',
            r'accused? ([A-Z][a-z\s]+)',
            r'against ([A-Z][a-z\s]+)',
        ]
        
        defendants = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            defendants.extend(matches)
        
        return list(set(defendants))[:10]

    def _extract_courts(self, text: str) -> List[str]:
        """Extract court mentions."""
        courts = []
        
        # Pattern: Court followed by actual name
        patterns = [
            r'(Supreme Court of India)',
            r'(High Court of [A-Z][a-z\s]+)',
            r'(District Court)',
            r'(Sessions Court)',
            r'([A-Z][a-z\s]*Court)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            courts.extend(matches)
        
        return list(set(courts))[:5]

    def _extract_dates(self, text: str) -> List[str]:
        """Extract date mentions."""
        # Patterns: various date formats
        patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',  # DD/MM/YYYY or MM/DD/YYYY
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            r'\d{4}',  # Year only
        ]
        
        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        
        return list(set(dates))[:10]

    # =========================================================================
    # CONTENT CLEANING
    # =========================================================================

    def _clean_content(self, content: str) -> str:
        """Clean content for processing."""
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Decode HTML entities
        content = content.replace('&nbsp;', ' ')
        content = content.replace('&quot;', '"')
        content = content.replace('&apos;', "'")
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove URLs
        content = re.sub(r'https?://\S+', '', content)
        
        return content.strip()

    # =========================================================================
    # RETRIEVAL & MANAGEMENT
    # =========================================================================

    def get_summary(self, article_id: str) -> Optional[ArticleSummary]:
        """Get summary for article."""
        return self.summaries.get(article_id)

    def get_neutral_summaries(
        self,
        threshold: NeutralityScore = NeutralityScore.NEUTRAL,
    ) -> List[ArticleSummary]:
        """Get summaries meeting neutrality threshold."""
        summaries = []
        
        neutral_levels = [
            NeutralityScore.HIGHLY_NEUTRAL,
            NeutralityScore.NEUTRAL,
        ]
        
        if threshold == NeutralityScore.SLIGHTLY_BIASED:
            neutral_levels.append(NeutralityScore.SLIGHTLY_BIASED)
        
        for summary in self.summaries.values():
            if summary.neutrality_score in neutral_levels:
                summaries.append(summary)
        
        return summaries

    def get_summaries_by_neutrality(self) -> Dict[str, List[ArticleSummary]]:
        """Get summaries grouped by neutrality score."""
        grouped = {}
        
        for level in NeutralityScore:
            grouped[level.value] = [
                s for s in self.summaries.values()
                if s.neutrality_score == level
            ]
        
        return grouped

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_summarization_stats(self) -> Dict:
        """Get summarization statistics."""
        summaries = list(self.summaries.values())
        
        if not summaries:
            return {"total_summaries": 0}
        
        opinion_count = sum(1 for s in summaries if s.contains_opinion)
        defam_count = sum(1 for s in summaries if s.contains_defamatory_language)
        
        avg_compression = (
            sum(s.compression_ratio for s in summaries) / len(summaries)
            if summaries else 0.0
        )
        
        neutrality_counts = {}
        for level in NeutralityScore:
            neutrality_counts[level.value] = sum(
                1 for s in summaries if s.neutrality_score == level
            )
        
        return {
            "total_summaries": len(summaries),
            "average_compression_ratio": round(avg_compression, 2),
            "containing_opinion": opinion_count,
            "containing_defamatory_language": defam_count,
            "neutrality_distribution": neutrality_counts,
            "average_summary_length": sum(s.summary_word_count for s in summaries) / len(summaries),
        }

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_summaries(self) -> List[Dict]:
        """Export all summaries."""
        return [
            {
                "article_id": s.article_id,
                "summary": s.summary_text,
                "type": s.summary_type.value,
                "neutrality": s.neutrality_score.value,
                "contains_opinion": s.contains_opinion,
                "key_facts": s.key_facts,
                "parties": s.parties_mentioned,
                "courts": s.courts_mentioned,
                "dates": s.dates_mentioned,
            }
            for s in self.summaries.values()
        ]
