"""
Deduplication Engine
Detects and handles syndicated, repeated, and similar articles

Groups similar content to avoid redundancy.
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import difflib
import hashlib


@dataclass
class DuplicateGroup:
    """Group of duplicate or near-duplicate articles."""
    
    group_id: str
    primary_article_id: str
    duplicate_article_ids: List[str]
    similarity_scores: Dict[str, float]  # article_id -> similarity (0-1)
    duplicate_type: str  # exact, syndicated, paraphrased, near_duplicate
    detection_timestamp: datetime
    notes: str = ""


class DeduplicationEngine:
    """Engine for detecting and managing duplicate articles."""

    def __init__(self):
        """Initialize deduplication engine."""
        self.duplicate_groups: Dict[str, DuplicateGroup] = {}
        self.article_to_group: Dict[str, str] = {}  # article_id -> group_id

    # =========================================================================
    # DUPLICATE DETECTION STRATEGIES
    # =========================================================================

    def detect_duplicates(
        self,
        articles: Dict[str, Dict],  # article_id -> article_data
        similarity_threshold: float = 0.85,
    ) -> List[DuplicateGroup]:
        """
        Detect duplicate/near-duplicate articles.
        
        Args:
            articles: Dictionary of articles
            similarity_threshold: Threshold for considering articles similar (0-1)
        
        Returns:
            List of duplicate groups found
        """
        duplicate_groups = []
        processed_ids = set()

        article_list = list(articles.items())
        
        for i, (id1, article1) in enumerate(article_list):
            if id1 in processed_ids:
                continue

            duplicate_articles = {id1: 1.0}  # article_id -> similarity
            
            # Compare with all remaining articles
            for id2, article2 in article_list[i + 1:]:
                if id2 in processed_ids:
                    continue

                # Check multiple similarity metrics
                similarity = self._compute_similarity(article1, article2)
                
                if similarity >= similarity_threshold:
                    duplicate_articles[id2] = similarity
                    processed_ids.add(id2)

            # If found duplicates, create group
            if len(duplicate_articles) > 1:
                group = self._create_duplicate_group(
                    id1, duplicate_articles, articles
                )
                duplicate_groups.append(group)
                
                for dup_id in duplicate_articles.keys():
                    self.article_to_group[dup_id] = group.group_id
                    processed_ids.add(dup_id)
                
                self.duplicate_groups[group.group_id] = group

        return duplicate_groups

    def _compute_similarity(self, article1: Dict, article2: Dict) -> float:
        """
        Compute similarity between two articles (0-1).
        
        Uses multiple strategies:
        - Title similarity
        - Content hash similarity
        - Publication date proximity
        - Source comparison
        """
        
        scores = []
        
        # Strategy 1: Title similarity (high weight)
        title1 = article1.get("title", "").lower()
        title2 = article2.get("title", "").lower()
        title_score = difflib.SequenceMatcher(None, title1, title2).ratio()
        scores.append(title_score * 0.4)
        
        # Strategy 2: Content similarity (high weight)
        content1 = f"{article1.get('title', '')} {article1.get('summary', '')}".lower()
        content2 = f"{article2.get('title', '')} {article2.get('summary', '')}".lower()
        content_score = difflib.SequenceMatcher(None, content1, content2).ratio()
        scores.append(content_score * 0.35)
        
        # Strategy 3: Temporal proximity (lower weight)
        date1 = article1.get("publication_date")
        date2 = article2.get("publication_date")
        temporal_score = 0.0
        if date1 and date2:
            days_diff = abs((date1 - date2).days)
            # More recent = higher score
            if days_diff <= 1:
                temporal_score = 1.0
            elif days_diff <= 7:
                temporal_score = 1.0 - (days_diff / 7) * 0.5
            else:
                temporal_score = 0.0
        scores.append(temporal_score * 0.15)
        
        # Strategy 4: Same source = likely syndication
        source1 = article1.get("source_id", "")
        source2 = article2.get("source_id", "")
        source_score = 0.0 if source1 != source2 else 0.5
        scores.append(source_score * 0.10)
        
        final_score = sum(scores)
        return min(1.0, final_score)

    def _create_duplicate_group(
        self,
        primary_id: str,
        similar_articles: Dict[str, float],
        articles: Dict[str, Dict],
    ) -> DuplicateGroup:
        """Create duplicate group from similar articles."""
        
        # Determine duplicate type
        primary = articles.get(primary_id, {})
        dup_ids = [id for id in similar_articles.keys() if id != primary_id]
        
        # Check for exact content match
        is_exact = all(
            similar_articles.get(dup_id, 0) > 0.99
            for dup_id in dup_ids
        )
        
        # Check for content from same time frame (indicator of syndication)
        is_syndicated = all(
            self._is_same_publication_window(primary, articles.get(dup_id, {}))
            for dup_id in dup_ids
        )
        
        if is_exact:
            dup_type = "exact"
        elif is_syndicated:
            dup_type = "syndicated"
        elif all(sim > 0.95 for sim in similar_articles.values()):
            dup_type = "paraphrased"
        else:
            dup_type = "near_duplicate"
        
        group_id = self._generate_group_id(primary_id, dup_ids)
        
        return DuplicateGroup(
            group_id=group_id,
            primary_article_id=primary_id,
            duplicate_article_ids=dup_ids,
            similarity_scores=similar_articles,
            duplicate_type=dup_type,
            detection_timestamp=datetime.now(),
            notes=f"Detected as {dup_type}",
        )

    @staticmethod
    def _is_same_publication_window(
        article1: Dict,
        article2: Dict,
        window_hours: int = 24,
    ) -> bool:
        """Check if articles published within same time window."""
        date1 = article1.get("publication_date")
        date2 = article2.get("publication_date")
        
        if not date1 or not date2:
            return False
        
        diff = abs((date1 - date2).total_seconds() / 3600)
        return diff <= window_hours

    @staticmethod
    def _generate_group_id(primary_id: str, duplicate_ids: List[str]) -> str:
        """Generate unique group ID."""
        combined = f"{primary_id}_{'_'.join(sorted(duplicate_ids))}"
        return hashlib.sha256(combined.encode()).hexdigest()[:12]

    # =========================================================================
    # DUPLICATE MANAGEMENT
    # =========================================================================

    def mark_primary(self, group_id: str, article_id: str) -> bool:
        """Mark article as primary in duplicate group."""
        if group_id not in self.duplicate_groups:
            return False

        group = self.duplicate_groups[group_id]
        
        # Add to group if not already there
        if article_id not in group.duplicate_article_ids and article_id != group.primary_article_id:
            return False
        
        # Swap with current primary
        if article_id in group.duplicate_article_ids:
            group.duplicate_article_ids.remove(article_id)
            group.duplicate_article_ids.append(group.primary_article_id)
            group.primary_article_id = article_id
            group.detection_timestamp = datetime.now()

        return True

    def consolidate_duplicates(
        self,
        group_id: str,
        keep_article_id: str,
        action: str = "archive",  # archive, merge, delete
    ) -> bool:
        """
        Consolidate duplicate articles.
        
        Args:
            group_id: ID of duplicate group
            keep_article_id: Article to keep
            action: What to do with duplicates (archive, merge, delete)
        """
        if group_id not in self.duplicate_groups:
            return False

        group = self.duplicate_groups[group_id]
        
        # Mark kept article as primary
        self.mark_primary(group_id, keep_article_id)
        
        # Update group status
        group.notes = f"Consolidated: {action} action taken on duplicates"
        
        return True

    def get_deduplicated_articles(
        self,
        articles: Dict[str, Dict],
    ) -> Dict[str, Dict]:
        """
        Return articles with duplicates removed.
        
        Returns only primary article from each duplicate group.
        """
        result = {}
        
        for article_id, article in articles.items():
            # If article is not in any group, include it
            if article_id not in self.article_to_group:
                result[article_id] = article
            else:
                # If it's in a group, include only if it's the primary
                group_id = self.article_to_group[article_id]
                group = self.duplicate_groups[group_id]
                
                if article_id == group.primary_article_id:
                    # Add duplicate count to article metadata
                    article_copy = article.copy()
                    article_copy["duplicate_count"] = len(group.duplicate_article_ids)
                    article_copy["duplicate_group_id"] = group_id
                    result[article_id] = article_copy

        return result

    # =========================================================================
    # SYNDICATION DETECTION
    # =========================================================================

    def detect_syndicated_content(
        self,
        articles: Dict[str, Dict],
    ) -> List[Tuple[str, List[str]]]:
        """
        Detect syndicated articles (same content published by multiple sources).
        
        Returns:
            List of (original_source, [republishing_sources])
        """
        syndication_patterns = []
        
        # Group articles by content hash
        content_groups = {}
        for article_id, article in articles.items():
            content_hash = self._compute_content_hash(article)
            
            if content_hash not in content_groups:
                content_groups[content_hash] = []
            content_groups[content_hash].append((article_id, article))
        
        # Find groups with same content from different sources
        for content_hash, group in content_groups.items():
            if len(group) > 1:
                sources = set()
                articles_by_source = {}
                
                for article_id, article in group:
                    source = article.get("source_id")
                    sources.add(source)
                    
                    if source not in articles_by_source:
                        articles_by_source[source] = []
                    articles_by_source[source].append(article)
                
                if len(sources) > 1:
                    # Find original (earliest published)
                    earliest_source = min(
                        articles_by_source.keys(),
                        key=lambda s: min(
                            a.get("publication_date", datetime.now())
                            for a in articles_by_source[s]
                        )
                    )
                    
                    other_sources = [s for s in sources if s != earliest_source]
                    syndication_patterns.append((earliest_source, other_sources))
        
        return syndication_patterns

    @staticmethod
    def _compute_content_hash(article: Dict) -> str:
        """Compute hash of article content."""
        content = f"{article.get('title', '')}_{article.get('summary', '')}"
        # Normalize whitespace
        content = ' '.join(content.split())
        return hashlib.md5(content.encode()).hexdigest()

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_deduplication_stats(self) -> Dict:
        """Get deduplication statistics."""
        all_groups = list(self.duplicate_groups.values())
        
        type_counts = {}
        for group in all_groups:
            dup_type = group.duplicate_type
            type_counts[dup_type] = type_counts.get(dup_type, 0) + 1
        
        total_duplicates = sum(
            len(group.duplicate_article_ids) for group in all_groups
        )
        
        avg_group_size = (
            (len(all_groups) + total_duplicates) / len(all_groups)
            if all_groups else 0
        )
        
        return {
            "total_duplicate_groups": len(all_groups),
            "total_duplicate_articles": total_duplicates,
            "by_type": type_counts,
            "average_group_size": avg_group_size,
        }

    # =========================================================================
    # EXPORT & CLEANUP
    # =========================================================================

    def export_duplicate_groups(self) -> List[Dict]:
        """Export duplicate groups."""
        return [
            {
                "group_id": group.group_id,
                "primary_article_id": group.primary_article_id,
                "duplicate_count": len(group.duplicate_article_ids),
                "duplicate_type": group.duplicate_type,
                "average_similarity": (
                    sum(group.similarity_scores.values()) / len(group.similarity_scores)
                ),
                "detection_timestamp": group.detection_timestamp.isoformat(),
            }
            for group in self.duplicate_groups.values()
        ]

    def clear_old_duplicates(self, days: int = 30) -> int:
        """Remove duplicate group records older than N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        to_delete = [
            group_id for group_id, group in self.duplicate_groups.items()
            if group.detection_timestamp < cutoff_date
        ]
        
        for group_id in to_delete:
            del self.duplicate_groups[group_id]
        
        return len(to_delete)
