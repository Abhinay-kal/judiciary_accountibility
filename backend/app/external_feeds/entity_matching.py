"""
Case Matching Engine
Links ingested articles to court cases using multiple matching strategies

Supports fuzzy matching with confidence scoring.
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from datetime import datetime


class MatchingStrategy(str, Enum):
    """Strategy used for matching article to case."""
    CASE_NUMBER = "case_number"
    PARTY_NAME = "party_name"
    JUDGE_NAME = "judge_name"
    COURT_NAME = "court_name"
    KEYWORD_FUZZY = "keyword_fuzzy"
    TEMPORAL_PROXIMITY = "temporal_proximity"
    COMBINED = "combined"


@dataclass
class MatchCandidate:
    """Potential match between article and case."""
    
    article_id: str
    case_id: str
    strategy: MatchingStrategy
    confidence_score: float  # 0.0-1.0
    strategy_scores: Dict[str, float] = None  # Scores from each strategy
    evidence: List[str] = None  # Explanation of match
    matched_by: str = None  # User or system
    is_verified: bool = False
    verification_timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.strategy_scores is None:
            self.strategy_scores = {}
        if self.evidence is None:
            self.evidence = []


class CaseMatchingEngine:
    """Engine for matching articles to cases."""

    def __init__(self, case_database = None):
        """
        Initialize matching engine.
        
        Args:
            case_database: Access to case records from main tracker
        """
        self.case_database = case_database
        self.matches: Dict[Tuple[str, str], MatchCandidate] = {}
        self.case_number_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict:
        """Compile regex patterns for case matching."""
        return {
            "case_number_format": re.compile(
                r'(\d{1,4})/(\d{4})',  # Format: 123/2023
                re.IGNORECASE
            ),
            "party_separator": re.compile(r'\bv[s]?\b', re.IGNORECASE),
            "judge_title": re.compile(r'(?:Justice|Judge|J\.|Shri|Smt\.)\s+(\w+(?:\s+\w+)?)', re.IGNORECASE),
            "court_keywords": re.compile(
                r'(?:District Court|High Court|Supreme Court|Sessions Court|Civil Court|Criminal Court|Court of Magistrate)',
                re.IGNORECASE
            ),
        }

    # =========================================================================
    # MAIN MATCHING INTERFACE
    # =========================================================================

    def find_matches(
        self,
        article: Dict,
        min_confidence: float = 0.60,
        limit: int = 5,
    ) -> List[MatchCandidate]:
        """
        Find matching cases for article using multiple strategies.
        
        Args:
            article: Article data with title, summary, etc.
            min_confidence: Minimum confidence threshold
            limit: Max number of matches to return
        
        Returns:
            List of MatchCandidate objects
        """
        all_matches = []

        # Strategy 1: Direct case number matching
        matches = self._match_by_case_number(article)
        all_matches.extend(matches)

        # Strategy 2: Party name matching
        matches = self._match_by_party_names(article)
        all_matches.extend(matches)

        # Strategy 3: Judge name matching
        matches = self._match_by_judge_name(article)
        all_matches.extend(matches)

        # Strategy 4: Court name matching
        matches = self._match_by_court_name(article)
        all_matches.extend(matches)

        # Strategy 5: Fuzzy keyword matching
        matches = self._match_by_keywords(article)
        all_matches.extend(matches)

        # Filter by confidence and deduplicate
        filtered_matches = self._deduplicate_matches(all_matches)
        filtered_matches = [
            m for m in filtered_matches
            if m.confidence_score >= min_confidence
        ]

        # Sort by confidence score
        filtered_matches = sorted(
            filtered_matches,
            key=lambda m: m.confidence_score,
            reverse=True
        )[:limit]

        return filtered_matches

    # =========================================================================
    # INDIVIDUAL MATCHING STRATEGIES
    # =========================================================================

    def _match_by_case_number(self, article: Dict) -> List[MatchCandidate]:
        """Match articles containing exact case numbers."""
        articles_text = f"{article.get('title', '')} {article.get('summary', '')}"
        matches = []

        # Find all case numbers in text
        case_numbers = self.case_number_patterns["case_number_format"].findall(articles_text)
        
        for case_num, year in case_numbers:
            case_number = f"{case_num}/{year}"
            
            if self.case_database:
                case = self.case_database.find_case_by_number(case_number)
                if case:
                    match = MatchCandidate(
                        article_id=article.get("id"),
                        case_id=case.get("case_id"),
                        strategy=MatchingStrategy.CASE_NUMBER,
                        confidence_score=0.98,  # Highest confidence for exact match
                        evidence=[f"Exact case number match: {case_number}"],
                    )
                    matches.append(match)

        return matches

    def _match_by_party_names(self, article: Dict) -> List[MatchCandidate]:
        """Match articles containing party names."""
        articles_text = f"{article.get('title', '')} {article.get('summary', '')}"
        text_lower = articles_text.lower()
        matches = []

        if not self.case_database:
            return matches

        # Get all unique party names from database
        all_cases = self.case_database.get_all_cases() if hasattr(self.case_database, 'get_all_cases') else []
        
        for case in all_cases:
            plaintiff = case.get("plaintiff_name", "").lower()
            defendant = case.get("defendant_name", "").lower()
            
            if not plaintiff and not defendant:
                continue

            # Score based on party matches
            score = 0.0
            evidence = []
            
            if plaintiff and len(plaintiff) > 3 and plaintiff in text_lower:
                score += 0.4
                evidence.append(f"Plaintiff name match: {plaintiff}")
            
            if defendant and len(defendant) > 3 and defendant in text_lower:
                score += 0.4
                evidence.append(f"Defendant name match: {defendant}")
            
            if score > 0:
                match = MatchCandidate(
                    article_id=article.get("id"),
                    case_id=case.get("case_id"),
                    strategy=MatchingStrategy.PARTY_NAME,
                    confidence_score=min(0.85, score),
                    evidence=evidence,
                )
                if match.confidence_score > 0.5:
                    matches.append(match)

        return matches

    def _match_by_judge_name(self, article: Dict) -> List[MatchCandidate]:
        """Match articles mentioning judge names."""
        article_text = f"{article.get('title', '')} {article.get('summary', '')}"
        judges = self.case_number_patterns["judge_title"].findall(article_text)
        matches = []

        if not self.case_database or not judges:
            return matches

        for judge_name in judges:
            cases = self.case_database.find_cases_by_judge(judge_name) if hasattr(
                self.case_database, 'find_cases_by_judge'
            ) else []
            
            for case in cases:
                match = MatchCandidate(
                    article_id=article.get("id"),
                    case_id=case.get("case_id"),
                    strategy=MatchingStrategy.JUDGE_NAME,
                    confidence_score=0.75,
                    evidence=[f"Judge mentioned: {judge_name}"],
                )
                matches.append(match)

        return matches

    def _match_by_court_name(self, article: Dict) -> List[MatchCandidate]:
        """Match articles by mentioned court names."""
        article_text = f"{article.get('title', '')} {article.get('summary', '')}"
        courts = self.case_number_patterns["court_keywords"].findall(article_text)
        matches = []

        if not self.case_database or not courts:
            return matches

        for court_name in courts:
            cases = self.case_database.find_cases_by_court(court_name) if hasattr(
                self.case_database, 'find_cases_by_court'
            ) else []
            
            # High volume of cases per court, lower confidence
            for case in cases[:5]:  # Limit to top 5
                match = MatchCandidate(
                    article_id=article.get("id"),
                    case_id=case.get("case_id"),
                    strategy=MatchingStrategy.COURT_NAME,
                    confidence_score=0.45,  # Lower confidence as multiple cases per court
                    evidence=[f"Court mentioned: {court_name}"],
                )
                matches.append(match)

        return matches

    def _match_by_keywords(self, article: Dict) -> List[MatchCandidate]:
        """Fuzzy match based on keywords and temporal proximity."""
        article_text = f"{article.get('title', '')} {article.get('summary', '')}"
        pub_date = article.get("publication_date")
        matches = []

        if not self.case_database:
            return matches

        # Extract keywords (simple approach: words > 4 chars)
        keywords = [
            word for word in re.findall(r'\b\w+\b', article_text.lower())
            if len(word) > 4 and word not in self._get_stopwords()
        ]

        if not keywords:
            return matches

        all_cases = self.case_database.get_all_cases() if hasattr(self.case_database, 'get_all_cases') else []
        
        for case in all_cases:
            case_text = f"{case.get('subject_matter', '')} {case.get('case_type', '')}"
            case_text_lower = case_text.lower()
            
            # Count keyword matches
            matching_keywords = [
                kw for kw in keywords
                if kw in case_text_lower
            ]
            
            if not matching_keywords:
                continue
            
            # Calculate keyword match score
            keyword_score = len(matching_keywords) / len(keywords)
            
            # Temporal proximity bonus (if dates are close)
            temporal_score = 0.0
            if pub_date and case.get("filed_date"):
                from datetime import timedelta
                try:
                    days_diff = abs((pub_date - case.get("filed_date")).days)
                    if days_diff < 90:
                        temporal_score = 0.3 * (1 - days_diff / 90)
                except:
                    pass
            
            combined_score = keyword_score * 0.7 + temporal_score * 0.3
            
            if combined_score > 0.4:
                match = MatchCandidate(
                    article_id=article.get("id"),
                    case_id=case.get("case_id"),
                    strategy=MatchingStrategy.KEYWORD_FUZZY,
                    confidence_score=min(0.80, combined_score),
                    evidence=[
                        f"Keywords matched: {', '.join(matching_keywords[:3])}",
                        f"Case type: {case.get('case_type')}",
                    ],
                )
                matches.append(match)

        return matches

    # =========================================================================
    # MATCH MANAGEMENT
    # =========================================================================

    def _deduplicate_matches(self, matches: List[MatchCandidate]) -> List[MatchCandidate]:
        """Remove duplicate matches, keeping highest confidence."""
        unique_matches = {}
        
        for match in matches:
            key = (match.article_id, match.case_id)
            
            if key not in unique_matches:
                unique_matches[key] = match
            else:
                # Keep match with higher confidence
                if match.confidence_score > unique_matches[key].confidence_score:
                    unique_matches[key] = match

        return list(unique_matches.values())

    def store_match(self, match: MatchCandidate) -> bool:
        """Store match in registry."""
        key = (match.article_id, match.case_id)
        self.matches[key] = match
        return True

    def get_match(self, article_id: str, case_id: str) -> Optional[MatchCandidate]:
        """Retrieve stored match."""
        key = (article_id, case_id)
        return self.matches.get(key)

    def get_matches_for_article(self, article_id: str) -> List[MatchCandidate]:
        """Get all matches for specific article."""
        return [
            match for match in self.matches.values()
            if match.article_id == article_id
        ]

    def get_matches_for_case(self, case_id: str) -> List[MatchCandidate]:
        """Get all matches for specific case."""
        return [
            match for match in self.matches.values()
            if match.case_id == case_id
        ]

    def verify_match(self, article_id: str, case_id: str, verified: bool = True) -> bool:
        """Manually verify or unverify a match."""
        match = self.get_match(article_id, case_id)
        if match:
            match.is_verified = verified
            match.verification_timestamp = datetime.now()
            return True
        return False

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_matching_stats(self) -> Dict:
        """Get matching engine statistics."""
        all_matches = list(self.matches.values())
        
        strategy_counts = {}
        for match in all_matches:
            strategy = match.strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        avg_confidence = (
            sum(m.confidence_score for m in all_matches) / len(all_matches)
            if all_matches else 0
        )

        return {
            "total_matches": len(all_matches),
            "verified_matches": sum(1 for m in all_matches if m.is_verified),
            "by_strategy": strategy_counts,
            "average_confidence_score": avg_confidence,
            "high_confidence_matches": sum(1 for m in all_matches if m.confidence_score >= 0.85),
        }

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _get_stopwords() -> set:
        """Common English stopwords to exclude from matching."""
        return {
            'the', 'a', 'and', 'or', 'is', 'was', 'in', 'of', 'to', 'for',
            'that', 'this', 'are', 'be', 'have', 'has', 'been', 'being',
            'from', 'with', 'by', 'case', 'court', 'judge', 'order'
        }

    def export_matches(self) -> List[Dict]:
        """Export all matches as dictionaries."""
        return [
            {
                "article_id": match.article_id,
                "case_id": match.case_id,
                "strategy": match.strategy.value,
                "confidence_score": match.confidence_score,
                "is_verified": match.is_verified,
                "evidence": match.evidence,
            }
            for match in self.matches.values()
        ]
