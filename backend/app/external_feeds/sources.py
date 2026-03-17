"""
External Feed Source Registry
Maintains registry of credible media, NGO, and government sources

Tracks source metadata for content credibility assessment.
"""

from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import hashlib


class OrganizationType(str, Enum):
    """Type of external organization."""
    MEDIA = "media"
    NGO = "ngo"
    GOVERNMENT = "government"
    RESEARCH = "research"
    LEGAL_WATCHDOG = "legal_watchdog"
    OTHER = "other"


class VerificationStatus(str, Enum):
    """Verification status of source."""
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNVERIFIED = "unverified"
    DEPRECATED = "deprecated"


class GeographicScope(str, Enum):
    """Geographic coverage of source."""
    NATIONAL = "national"
    REGIONAL = "regional"
    LOCAL = "local"
    INTERNATIONAL = "international"


@dataclass
class SourceMetadata:
    """Metadata for external source."""
    
    source_name: str
    organization_type: OrganizationType
    country: str = "India"
    verification_status: VerificationStatus = VerificationStatus.PROVISIONAL
    credibility_score: float = 0.5  # 0.0-1.0
    bias_label: Optional[str] = None  # "left", "center", "right", "neutral"
    geographic_scope: GeographicScope = GeographicScope.NATIONAL
    language: str = "english"
    
    # Contact & operational info
    website_url: Optional[str] = None
    contact_email: Optional[str] = None
    api_endpoint: Optional[str] = None
    rss_feeds: List[str] = None
    
    # Operational metadata
    active: bool = True
    ingest_enabled: bool = True
    last_ingestion_date: Optional[datetime] = None
    articles_ingested: int = 0
    
    # Quality metrics
    false_positive_rate: float = 0.0  # Fraction of articles not related to cases
    duplicate_rate: float = 0.0  # Fraction of duplicated content
    accuracy_score: float = 1.0  # Fraction of correctly matched cases
    
    # Additional metadata
    notable_investigations: Optional[str] = None  # Brief description
    founded_year: Optional[int] = None
    editor_chief: Optional[str] = None
    description: Optional[str] = None
    
    date_added: datetime = None
    date_modified: datetime = None

    def __post_init__(self):
        if self.rss_feeds is None:
            self.rss_feeds = []
        if self.date_added is None:
            self.date_added = datetime.now()
        if self.date_modified is None:
            self.date_modified = datetime.now()

    def get_source_id(self) -> str:
        """Generate deterministic source ID."""
        return hashlib.sha256(
            f"{self.source_name}_{self.organization_type.value}".encode()
        ).hexdigest()[:16]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["organization_type"] = self.organization_type.value
        data["verification_status"] = self.verification_status.value
        data["geographic_scope"] = self.geographic_scope.value
        data["date_added"] = self.date_added.isoformat() if self.date_added else None
        data["date_modified"] = self.date_modified.isoformat() if self.date_modified else None
        data["last_ingestion_date"] = (
            self.last_ingestion_date.isoformat() if self.last_ingestion_date else None
        )
        return data


class SourceRegistry:
    """Registry of external content sources."""

    # Pre-defined credible sources
    FEATURED_SOURCES = {
        "the_hindu": SourceMetadata(
            source_name="The Hindu",
            organization_type=OrganizationType.MEDIA,
            credibility_score=0.95,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://www.thehindu.com",
            rss_feeds=["https://www.thehindu.com/news/national/feed"],
            founded_year=1878,
            description="Leading English-language newspaper with strong legal/judicial coverage",
        ),
        "the_wire": SourceMetadata(
            source_name="The Wire",
            organization_type=OrganizationType.MEDIA,
            credibility_score=0.93,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://thewire.in",
            founded_year=2015,
            description="Digital news platform with investigative journalism focus",
        ),
        "bar_council_india": SourceMetadata(
            source_name="Bar Council of India",
            organization_type=OrganizationType.LEGAL_WATCHDOG,
            credibility_score=0.98,
            verification_status=VerificationStatus.VERIFIED,
            geographic_scope=GeographicScope.NATIONAL,
            website_url="https://www.barcouncilofindia.org",
            description="Official regulatory body for Indian legal profession",
        ),
        "human_rights_watch": SourceMetadata(
            source_name="Human Rights Watch",
            organization_type=OrganizationType.NGO,
            credibility_score=0.94,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://www.hrw.org",
            description="International NGO monitoring human rights and justice issues",
        ),
        "amnesty_international": SourceMetadata(
            source_name="Amnesty International",
            organization_type=OrganizationType.NGO,
            credibility_score=0.93,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://www.amnesty.org",
            description="Global human rights organization with India focus",
        ),
        "supreme_court_india": SourceMetadata(
            source_name="Supreme Court of India",
            organization_type=OrganizationType.GOVERNMENT,
            credibility_score=1.0,
            verification_status=VerificationStatus.VERIFIED,
            geographic_scope=GeographicScope.NATIONAL,
            website_url="https://www.sci.gov.in",
            description="Official Supreme Court website and case databases",
        ),
        "indian_express": SourceMetadata(
            source_name="Indian Express",
            organization_type=OrganizationType.MEDIA,
            credibility_score=0.92,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://indianexpress.com",
            founded_year=1932,
            description="Major newspaper with extensive judicial reporting",
        ),
        "deccan_chronicle": SourceMetadata(
            source_name="Deccan Chronicle",
            organization_type=OrganizationType.MEDIA,
            credibility_score=0.88,
            verification_status=VerificationStatus.VERIFIED,
            geographic_scope=GeographicScope.REGIONAL,
            website_url="https://www.deccanchronicle.com",
            founded_year=1938,
            description="Regional newspaper covering South Indian courts",
        ),
        "indian_kanoon": SourceMetadata(
            source_name="Indian Kanoon",
            organization_type=OrganizationType.RESEARCH,
            credibility_score=0.96,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://indiankanoon.org",
            description="Free online legal database with case information",
        ),
        "prsindia": SourceMetadata(
            source_name="PRS Legislative Research",
            organization_type=OrganizationType.RESEARCH,
            credibility_score=0.95,
            verification_status=VerificationStatus.VERIFIED,
            website_url="https://prsindia.org",
            description="Provides legislative and policy analysis relevant to justice",
        ),
    }

    def __init__(self):
        """Initialize source registry."""
        self.sources: Dict[str, SourceMetadata] = {}
        self._load_featured_sources()

    def _load_featured_sources(self):
        """Load pre-defined featured sources."""
        for source_key, source in self.FEATURED_SOURCES.items():
            self.add_source(source)

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    def add_source(self, source: SourceMetadata) -> str:
        """
        Add source to registry.
        
        Returns:
            source_id
        """
        source_id = source.get_source_id()
        source.date_added = datetime.now()
        source.date_modified = datetime.now()
        self.sources[source_id] = source
        return source_id

    def get_source(self, source_id: str) -> Optional[SourceMetadata]:
        """Retrieve source by ID."""
        return self.sources.get(source_id)

    def get_source_by_name(self, source_name: str) -> Optional[SourceMetadata]:
        """Find source by name (case-insensitive)."""
        name_lower = source_name.lower()
        for source in self.sources.values():
            if source.source_name.lower() == name_lower:
                return source
        return None

    def update_source(self, source_id: str, updates: Dict) -> bool:
        """Update source metadata."""
        if source_id not in self.sources:
            return False

        source = self.sources[source_id]
        for key, value in updates.items():
            if hasattr(source, key):
                setattr(source, key, value)

        source.date_modified = datetime.now()
        return True

    def remove_source(self, source_id: str) -> bool:
        """Remove source from registry."""
        if source_id in self.sources:
            del self.sources[source_id]
            return True
        return False

    # =========================================================================
    # CREDIBILITY OPERATIONS
    # =========================================================================

    def get_credibility_score(self, source_id: str) -> Optional[float]:
        """Get credibility score for source."""
        source = self.get_source(source_id)
        if not source:
            return None

        # Calculate composite score based on verification and metrics
        base_score = source.credibility_score
        
        # Adjust for false positives
        false_positive_penalty = source.false_positive_rate * 0.15
        
        # Adjust for duplicates
        duplicate_penalty = source.duplicate_rate * 0.10
        
        # Adjust for matching accuracy
        accuracy_multiplier = source.accuracy_score
        
        final_score = (base_score - false_positive_penalty - duplicate_penalty) * accuracy_multiplier
        return max(0.0, min(1.0, final_score))

    def update_quality_metrics(
        self,
        source_id: str,
        false_positive_rate: Optional[float] = None,
        duplicate_rate: Optional[float] = None,
        accuracy_score: Optional[float] = None,
    ) -> bool:
        """Update quality metrics for source."""
        if source_id not in self.sources:
            return False

        source = self.sources[source_id]
        
        if false_positive_rate is not None:
            source.false_positive_rate = max(0.0, min(1.0, false_positive_rate))
        if duplicate_rate is not None:
            source.duplicate_rate = max(0.0, min(1.0, duplicate_rate))
        if accuracy_score is not None:
            source.accuracy_score = max(0.0, min(1.0, accuracy_score))

        source.date_modified = datetime.now()
        return True

    def record_ingestion(self, source_id: str, articles_count: int) -> bool:
        """Record successful ingestion event."""
        if source_id not in self.sources:
            return False

        source = self.sources[source_id]
        source.last_ingestion_date = datetime.now()
        source.articles_ingested += articles_count
        source.date_modified = datetime.now()
        return True

    # =========================================================================
    # FILTERING & SEARCH
    # =========================================================================

    def list_sources(
        self,
        org_type: Optional[OrganizationType] = None,
        verification: Optional[VerificationStatus] = None,
        active_only: bool = True,
    ) -> List[SourceMetadata]:
        """
        List sources with optional filtering.
        
        Args:
            org_type: Filter by organization type
            verification: Filter by verification status
            active_only: Only return active sources
        """
        results = list(self.sources.values())

        if active_only:
            results = [s for s in results if s.active]

        if org_type:
            results = [s for s in results if s.organization_type == org_type]

        if verification:
            results = [s for s in results if s.verification_status == verification]

        return sorted(results, key=lambda s: s.credibility_score, reverse=True)

    def get_verified_sources(self) -> List[SourceMetadata]:
        """Get all verified sources."""
        return self.list_sources(verification=VerificationStatus.VERIFIED)

    def get_media_sources(self) -> List[SourceMetadata]:
        """Get all media sources."""
        return self.list_sources(org_type=OrganizationType.MEDIA)

    def get_ngo_sources(self) -> List[SourceMetadata]:
        """Get all NGO sources."""
        return self.list_sources(org_type=OrganizationType.NGO)

    def get_high_credibility_sources(self, threshold: float = 0.85) -> List[SourceMetadata]:
        """Get sources above credibility threshold."""
        return [
            s for s in self.list_sources()
            if self.get_credibility_score(s.get_source_id()) >= threshold
        ]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        all_sources = list(self.sources.values())
        active_sources = [s for s in all_sources if s.active]

        org_type_counts = {}
        for source in all_sources:
            org_type = source.organization_type.value
            org_type_counts[org_type] = org_type_counts.get(org_type, 0) + 1

        return {
            "total_sources": len(all_sources),
            "active_sources": len(active_sources),
            "by_organization_type": org_type_counts,
            "verified_sources": sum(
                1 for s in all_sources
                if s.verification_status == VerificationStatus.VERIFIED
            ),
            "total_articles_ingested": sum(s.articles_ingested for s in all_sources),
            "average_credibility_score": (
                sum(s.credibility_score for s in all_sources) / len(all_sources)
                if all_sources else 0
            ),
        }

    # =========================================================================
    # EXPORT & IMPORT
    # =========================================================================

    def export_registry(self) -> List[Dict]:
        """Export all sources as dictionaries."""
        return [source.to_dict() for source in self.sources.values()]

    def import_sources_bulk(self, sources_data: List[Dict]) -> int:
        """Import multiple sources, return count added."""
        count = 0
        for source_dict in sources_data:
            try:
                # Parse enums
                org_type = OrganizationType[source_dict.get("organization_type", "OTHER").upper()]
                verify_status = VerificationStatus[
                    source_dict.get("verification_status", "UNVERIFIED").upper()
                ]
                geo_scope = GeographicScope[
                    source_dict.get("geographic_scope", "NATIONAL").upper()
                ]

                source = SourceMetadata(
                    source_name=source_dict["source_name"],
                    organization_type=org_type,
                    verification_status=verify_status,
                    credibility_score=source_dict.get("credibility_score", 0.5),
                    bias_label=source_dict.get("bias_label"),
                    geographic_scope=geo_scope,
                    website_url=source_dict.get("website_url"),
                    contact_email=source_dict.get("contact_email"),
                    api_endpoint=source_dict.get("api_endpoint"),
                    rss_feeds=source_dict.get("rss_feeds", []),
                )
                self.add_source(source)
                count += 1
            except (KeyError, ValueError):
                continue

        return count
