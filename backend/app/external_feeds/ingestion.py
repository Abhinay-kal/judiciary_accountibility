"""
External Feed Ingestion Pipeline
Collects articles from RSS feeds, APIs, and web scraping

Handles multiple data source types and formats.
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import re
from html import unescape


class ArticleStatus(str, Enum):
    """Status of ingested article."""
    RAW = "raw"
    NORMALIZED = "normalized"
    PROCESSED = "processed"
    MATCHED = "matched"
    REJECTED = "rejected"


class IngestionMethod(str, Enum):
    """Method used to ingest article."""
    RSS_FEED = "rss_feed"
    API = "api"
    WEB_SCRAPE = "web_scrape"
    MANUAL = "manual"
    DIRECT_SUBMISSION = "direct_submission"


@dataclass
class RawArticle:
    """Raw article as ingested from source."""
    
    source_id: str
    ingestion_method: IngestionMethod
    ingestion_date: datetime
    
    # Core metadata
    title: str
    publication_date: datetime
    author: Optional[str] = None
    url: Optional[str] = None
    
    # Content
    summary: Optional[str] = None
    full_text: Optional[str] = None
    
    # Source-provided metadata
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # Processing metadata
    status: ArticleStatus = ArticleStatus.RAW
    content_hash: str = ""
    language: str = "english"
    content_length: int = 0
    
    # Tracking
    processing_notes: List[str] = field(default_factory=list)
    created_at: datetime = None
    modified_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.modified_at is None:
            self.modified_at = datetime.now()
        
        # Compute content hash from title + url
        self._compute_hash()
        
        # Calculate content length
        if self.full_text:
            self.content_length = len(self.full_text)
        elif self.summary:
            self.content_length = len(self.summary)

    def _compute_hash(self):
        """Compute SHA256 hash of content."""
        content = f"{self.title}_{self.author}_{self.url}".lower()
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()

    def clean_html(self, text: Optional[str]) -> Optional[str]:
        """Remove HTML tags and decode entities."""
        if not text:
            return None
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = unescape(text)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def normalize_text(self):
        """Normalize text fields (remove HTML, etc)."""
        if self.summary:
            self.summary = self.clean_html(self.summary)
        if self.full_text:
            self.full_text = self.clean_html(self.full_text)
        if self.title:
            self.title = self.clean_html(self.title)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "ingestion_method": self.ingestion_method.value,
            "ingestion_date": self.ingestion_date.isoformat(),
            "title": self.title,
            "publication_date": self.publication_date.isoformat(),
            "author": self.author,
            "url": self.url,
            "summary": self.summary,
            "full_text": self.full_text[:500] + "..." if self.full_text and len(self.full_text) > 500 else self.full_text,
            "tags": self.tags,
            "categories": self.categories,
            "status": self.status.value,
            "content_hash": self.content_hash,
            "language": self.language,
            "content_length": self.content_length,
        }


class IngestionPipeline:
    """Pipeline for ingesting external articles."""

    def __init__(self):
        """Initialize ingestion pipeline."""
        self.articles: Dict[str, RawArticle] = {}
        self.failed_ingestions: List[Dict] = []

    # =========================================================================
    # RSS FEED INGESTION
    # =========================================================================

    def ingest_rss_feed(
        self,
        source_id: str,
        feed_url: str,
        max_articles: int = 50,
    ) -> Tuple[int, List[str]]:
        """
        Ingest articles from RSS feed.
        
        Returns:
            (articles_ingested, article_ids)
        """
        try:
            import feedparser
        except ImportError:
            return 0, []

        try:
            feed = feedparser.parse(feed_url)
            article_ids = []
            
            for entry in feed.entries[:max_articles]:
                try:
                    article = self._parse_rss_entry(source_id, entry)
                    article_id = self._store_article(article)
                    article_ids.append(article_id)
                except Exception as e:
                    self.failed_ingestions.append({
                        "source_id": source_id,
                        "feed_url": feed_url,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })
                    continue
            
            return len(article_ids), article_ids

        except Exception as e:
            self.failed_ingestions.append({
                "source_id": source_id,
                "feed_url": feed_url,
                "error": f"Feed parsing error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            })
            return 0, []

    def _parse_rss_entry(self, source_id: str, entry) -> RawArticle:
        """Parse individual RSS entry."""
        
        # Extract publication date
        pub_date = datetime.now()
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except:
                pass
        
        # Extract content
        summary = entry.get('summary', entry.get('description', ''))
        title = entry.get('title', 'Untitled')
        author = entry.get('author', None)
        url = entry.get('link', None)
        
        # Extract tags
        tags = []
        if hasattr(entry, 'tags'):
            tags = [tag.term for tag in entry.tags]
        
        article = RawArticle(
            source_id=source_id,
            ingestion_method=IngestionMethod.RSS_FEED,
            ingestion_date=datetime.now(),
            title=title,
            publication_date=pub_date,
            author=author,
            url=url,
            summary=summary,
            tags=tags,
        )
        
        return article

    # =========================================================================
    # API INGESTION
    # =========================================================================

    def ingest_from_api(
        self,
        source_id: str,
        api_endpoint: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Tuple[int, List[str]]:
        """
        Ingest articles from API endpoint.
        
        Returns:
            (articles_ingested, article_ids)
        """
        try:
            import requests
        except ImportError:
            return 0, []

        try:
            response = requests.get(api_endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            article_ids = []
            
            # Handle different API response formats
            articles_list = self._extract_articles_from_api_response(data)
            
            for article_data in articles_list:
                try:
                    article = self._parse_api_response(source_id, article_data)
                    article_id = self._store_article(article)
                    article_ids.append(article_id)
                except Exception as e:
                    self.failed_ingestions.append({
                        "source_id": source_id,
                        "api_endpoint": api_endpoint,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })
                    continue
            
            return len(article_ids), article_ids

        except Exception as e:
            self.failed_ingestions.append({
                "source_id": source_id,
                "api_endpoint": api_endpoint,
                "error": f"API error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            })
            return 0, []

    def _extract_articles_from_api_response(self, data: Dict) -> List[Dict]:
        """Extract articles list from API response."""
        # Handle common API response patterns
        if isinstance(data, list):
            return data
        
        if "articles" in data:
            return data["articles"]
        
        if "results" in data:
            return data["results"]
        
        if "data" in data:
            data_val = data["data"]
            if isinstance(data_val, list):
                return data_val
        
        return [data] if isinstance(data, dict) else []

    def _parse_api_response(self, source_id: str, item: Dict) -> RawArticle:
        """Parse API response item into RawArticle."""
        
        # Try to extract common field names
        title = (
            item.get("title") or
            item.get("headline") or
            item.get("name") or
            "Untitled"
        )
        
        pub_date_str = (
            item.get("publishedAt") or
            item.get("publication_date") or
            item.get("date") or
            item.get("published_at")
        )
        
        pub_date = datetime.now()
        if pub_date_str:
            try:
                # Try ISO format
                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
            except:
                try:
                    # Try common formats
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except:
                    pass
        
        summary = (
            item.get("description") or
            item.get("summary") or
            item.get("content") or
            ""
        )
        
        article = RawArticle(
            source_id=source_id,
            ingestion_method=IngestionMethod.API,
            ingestion_date=datetime.now(),
            title=title,
            publication_date=pub_date,
            author=item.get("author"),
            url=item.get("url") or item.get("link"),
            summary=summary,
            tags=item.get("tags", []),
        )
        
        return article

    # =========================================================================
    # MANUAL INGESTION
    # =========================================================================

    def ingest_manual(
        self,
        source_id: str,
        title: str,
        publication_date: datetime,
        url: Optional[str] = None,
        summary: Optional[str] = None,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Manually ingest a single article.
        
        Returns:
            article_id
        """
        article = RawArticle(
            source_id=source_id,
            ingestion_method=IngestionMethod.MANUAL,
            ingestion_date=datetime.now(),
            title=title,
            publication_date=publication_date,
            author=author,
            url=url,
            summary=summary,
            tags=tags or [],
        )
        
        return self._store_article(article)

    # =========================================================================
    # STORAGE & RETRIEVAL
    # =========================================================================

    def _store_article(self, article: RawArticle) -> str:
        """Store article and return ID."""
        article_id = article.content_hash
        article.normalize_text()
        self.articles[article_id] = article
        return article_id

    def get_article(self, article_id: str) -> Optional[RawArticle]:
        """Retrieve article by ID."""
        return self.articles.get(article_id)

    def get_articles_by_source(self, source_id: str) -> List[RawArticle]:
        """Get all articles from specific source."""
        return [
            article for article in self.articles.values()
            if article.source_id == source_id
        ]

    def get_articles_by_status(self, status: ArticleStatus) -> List[RawArticle]:
        """Get articles by processing status."""
        return [
            article for article in self.articles.values()
            if article.status == status
        ]

    def get_recent_articles(self, days: int = 7) -> List[RawArticle]:
        """Get articles from last N days."""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            article for article in self.articles.values()
            if article.publication_date >= cutoff_date
        ]

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def update_article_status(self, article_id: str, status: ArticleStatus) -> bool:
        """Update article processing status."""
        if article_id not in self.articles:
            return False
        
        self.articles[article_id].status = status
        self.articles[article_id].modified_at = datetime.now()
        return True

    def add_processing_note(self, article_id: str, note: str) -> bool:
        """Add processing note to article."""
        if article_id not in self.articles:
            return False
        
        self.articles[article_id].processing_notes.append(note)
        self.articles[article_id].modified_at = datetime.now()
        return True

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_ingestion_stats(self) -> Dict:
        """Get ingestion pipeline statistics."""
        all_articles = list(self.articles.values())
        
        status_counts = {}
        for article in all_articles:
            status = article.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        method_counts = {}
        for article in all_articles:
            method = article.ingestion_method.value
            method_counts[method] = method_counts.get(method, 0) + 1
        
        return {
            "total_articles": len(all_articles),
            "by_status": status_counts,
            "by_ingestion_method": method_counts,
            "failed_ingestions": len(self.failed_ingestions),
            "average_content_length": (
                sum(a.content_length for a in all_articles) / len(all_articles)
                if all_articles else 0
            ),
        }

    def get_failed_ingestions(self) -> List[Dict]:
        """Get list of failed ingestion attempts."""
        return self.failed_ingestions[-100:]  # Return last 100 failures

    # =========================================================================
    # EXPORT & CLEANUP
    # =========================================================================

    def export_articles(self, status: Optional[ArticleStatus] = None) -> List[Dict]:
        """Export articles as dictionaries."""
        articles = (
            self.get_articles_by_status(status)
            if status
            else list(self.articles.values())
        )
        return [article.to_dict() for article in articles]

    def clear_old_articles(self, days: int = 90) -> int:
        """Delete articles older than N days."""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        to_delete = [
            article_id for article_id, article in self.articles.items()
            if article.ingestion_date < cutoff_date
        ]
        
        for article_id in to_delete:
            del self.articles[article_id]
        
        return len(to_delete)
