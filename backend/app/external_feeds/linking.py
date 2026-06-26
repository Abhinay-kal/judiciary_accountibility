"""
External Reports Linking Module
Links external media coverage to court cases in the database

Integrates with case database to associate external reports.
"""

from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReportVerificationStatus(str, Enum):
    """Verification status of external report match."""
    AUTO_MATCHED = "auto_matched"  # Matched by algorithm
    MANUALLY_VERIFIED = "manually_verified"  # Verified by human
    DISPUTED = "disputed"  # Match is questionable
    REJECTED = "rejected"  # False positive
    PENDING_REVIEW = "pending_review"  # Awaiting manual review


class ReportRelevanceLevel(str, Enum):
    """How relevant the report is to the case."""
    PRIMARY = "primary"  # Core case coverage
    CONTEXTUAL = "contextual"  # Provides background/context
    RELATED = "related"  # Related but not direct
    MINIMAL = "minimal"  # Tangential mention


@dataclass
class ExternalReport:
    """Represents external media coverage of a case."""
    
    report_id: str
    case_id: str
    source_id: str
    source_name: str
    
    # Article data
    title: str
    url: str
    publication_date: datetime
    
    # Quality metrics
    match_confidence: float  # 0.0-1.0
    credibility_score: float  # 0.0-1.0
    
    # Content
    summary: Optional[str] = None
    full_text: Optional[str] = None
    
    relevance_level: "ReportRelevanceLevel" = ReportRelevanceLevel.RELATED
    
    # Verification
    verification_status: ReportVerificationStatus = ReportVerificationStatus.AUTO_MATCHED
    verified_by: Optional[str] = None
    verification_timestamp: Optional[datetime] = None
    
    # Metadata
    ingestion_timestamp: datetime = None
    external_url: Optional[str] = None
    original_language: str = "en"
    
    def __post_init__(self):
        if self.ingestion_timestamp is None:
            self.ingestion_timestamp = datetime.now()


class ExternalReportLinkingEngine:
    """Engine for linking external reports to court cases."""

    def __init__(self):
        """Initialize linking engine."""
        self.reports: Dict[str, ExternalReport] = {}
        self.case_reports: Dict[str, List[str]] = {}  # case_id -> list of report_ids
        self.source_reports: Dict[str, List[str]] = {}  # source_id -> list of report_ids
        self.verified_matches: int = 0
        self.disputed_matches: int = 0

    # =========================================================================
    # REPORT CREATION
    # =========================================================================

    def create_external_report(
        self,
        report_id: str,
        case_id: str,
        source_id: str,
        source_name: str,
        title: str,
        url: str,
        publication_date: datetime,
        match_confidence: float,
        credibility_score: float,
        summary: Optional[str] = None,
        full_text: Optional[str] = None,
        relevance_level: ReportRelevanceLevel = ReportRelevanceLevel.RELATED,
    ) -> ExternalReport:
        """
        Create and link external report to case.
        
        Args:
            report_id: Unique report ID
            case_id: Case to link to
            source_id: Source ID
            source_name: Source name
            title: Article title
            url: Article URL
            publication_date: When published
            match_confidence: Matching engine confidence (0-1)
            credibility_score: Source credibility (0-1)
            summary: Article summary
            full_text: Full article text
            relevance_level: How relevant to case
        
        Returns:
            ExternalReport
        """
        
        report = ExternalReport(
            report_id=report_id,
            case_id=case_id,
            source_id=source_id,
            source_name=source_name,
            title=title,
            url=url,
            publication_date=publication_date,
            summary=summary,
            full_text=full_text,
            match_confidence=match_confidence,
            credibility_score=credibility_score,
            relevance_level=relevance_level,
        )
        
        self.reports[report_id] = report
        
        # Index by case
        if case_id not in self.case_reports:
            self.case_reports[case_id] = []
        self.case_reports[case_id].append(report_id)
        
        # Index by source
        if source_id not in self.source_reports:
            self.source_reports[source_id] = []
        self.source_reports[source_id].append(report_id)
        
        return report

    # =========================================================================
    # REPORT RETRIEVAL
    # =========================================================================

    def get_report(self, report_id: str) -> Optional[ExternalReport]:
        """Get single report by ID."""
        return self.reports.get(report_id)

    def get_case_reports(
        self,
        case_id: str,
        verification_status: Optional[ReportVerificationStatus] = None,
    ) -> List[ExternalReport]:
        """
        Get all reports for case.
        
        Args:
            case_id: Case ID
            verification_status: Filter by status (optional)
        
        Returns:
            List of ExternalReports
        """
        if case_id not in self.case_reports:
            return []
        
        reports = [
            self.reports[report_id]
            for report_id in self.case_reports[case_id]
        ]
        
        if verification_status:
            reports = [
                r for r in reports
                if r.verification_status == verification_status
            ]
        
        # Sort by publication date DESC
        return sorted(reports, key=lambda r: r.publication_date, reverse=True)

    def get_source_reports(
        self,
        source_id: str,
        verified_only: bool = False,
    ) -> List[ExternalReport]:
        """Get all reports from source."""
        if source_id not in self.source_reports:
            return []
        
        reports = [
            self.reports[report_id]
            for report_id in self.source_reports[source_id]
        ]
        
        if verified_only:
            reports = [
                r for r in reports
                if r.verification_status == ReportVerificationStatus.MANUALLY_VERIFIED
            ]
        
        return reports

    # =========================================================================
    # VERIFICATION & STATUS UPDATES
    # =========================================================================

    def verify_report(
        self,
        report_id: str,
        verified_by: str,
        relevance_level: Optional[ReportRelevanceLevel] = None,
    ) -> bool:
        """Mark report as manually verified."""
        if report_id not in self.reports:
            return False
        
        report = self.reports[report_id]
        report.verification_status = ReportVerificationStatus.MANUALLY_VERIFIED
        report.verified_by = verified_by
        report.verification_timestamp = datetime.now()
        
        if relevance_level:
            report.relevance_level = relevance_level
        
        self.verified_matches += 1
        return True

    def dispute_report(self, report_id: str, reason: Optional[str] = None) -> bool:
        """Mark report as disputed."""
        if report_id not in self.reports:
            return False
        
        report = self.reports[report_id]
        report.verification_status = ReportVerificationStatus.DISPUTED
        self.disputed_matches += 1
        return True

    def reject_report(self, report_id: str, reason: Optional[str] = None) -> bool:
        """Mark report as rejected false positive."""
        if report_id not in self.reports:
            return False
        
        report = self.reports[report_id]
        report.verification_status = ReportVerificationStatus.REJECTED
        return True

    def update_relevance_level(
        self,
        report_id: str,
        relevance_level: ReportRelevanceLevel,
    ) -> bool:
        """Update relevance level of report."""
        if report_id not in self.reports:
            return False
        
        self.reports[report_id].relevance_level = relevance_level
        return True

    def update_credibility_score(
        self,
        report_id: str,
        new_score: float,
    ) -> bool:
        """Update credibility score based on new info."""
        if report_id not in self.reports:
            return False
        
        if not 0.0 <= new_score <= 1.0:
            return False
        
        self.reports[report_id].credibility_score = new_score
        return True

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def link_multiple_reports(
        self,
        case_id: str,
        articles: List[Dict],
        match_confidence: float,
    ) -> List[ExternalReport]:
        """Link multiple articles to case at once."""
        reports = []
        
        for i, article in enumerate(articles):
            report_id = f"rpt_{case_id}_{article.get('source_id', 'unknown')}_{i}"
            
            report = self.create_external_report(
                report_id=report_id,
                case_id=case_id,
                source_id=article.get("source_id", "unknown"),
                source_name=article.get("source_name", "Unknown Source"),
                title=article.get("title", ""),
                url=article.get("url", ""),
                publication_date=article.get("publication_date", datetime.now()),
                match_confidence=match_confidence,
                credibility_score=article.get("credibility_score", 0.5),
                summary=article.get("summary"),
                full_text=article.get("full_text"),
            )
            
            reports.append(report)
        
        return reports

    def unlink_report(self, report_id: str) -> bool:
        """Remove report link (soft delete by marking for removal)."""
        if report_id not in self.reports:
            return False
        
        report = self.reports[report_id]
        
        # Remove from indices
        if report.case_id in self.case_reports:
            self.case_reports[report.case_id].remove(report_id)
        
        if report.source_id in self.source_reports:
            self.source_reports[report.source_id].remove(report_id)
        
        # Mark as rejected
        report.verification_status = ReportVerificationStatus.REJECTED
        
        return True

    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================

    def get_linking_stats(self) -> Dict:
        """Get statistics on linked reports."""
        all_reports = list(self.reports.values())
        
        verification_counts = {
            "auto_matched": 0,
            "manually_verified": 0,
            "disputed": 0,
            "rejected": 0,
            "pending_review": 0,
        }
        
        for report in all_reports:
            verification_counts[report.verification_status.value] += 1
        
        relevance_counts = {
            "primary": 0,
            "contextual": 0,
            "related": 0,
            "minimal": 0,
        }
        
        for report in all_reports:
            relevance_counts[report.relevance_level.value] += 1
        
        return {
            "total_reports": len(all_reports),
            "cases_with_reports": len(self.case_reports),
            "sources_represented": len(self.source_reports),
            "verification_counts": verification_counts,
            "relevance_counts": relevance_counts,
            "average_confidence": (
                sum(r.match_confidence for r in all_reports) / len(all_reports)
                if all_reports else 0.0
            ),
            "average_credibility": (
                sum(r.credibility_score for r in all_reports) / len(all_reports)
                if all_reports else 0.0
            ),
        }

    def get_case_report_summary(self, case_id: str) -> Dict:
        """Get summary of all reports for case."""
        reports = self.get_case_reports(case_id)
        
        if not reports:
            return {"case_id": case_id, "total_reports": 0}
        
        verified = sum(
            1 for r in reports
            if r.verification_status == ReportVerificationStatus.MANUALLY_VERIFIED
        )
        
        return {
            "case_id": case_id,
            "total_reports": len(reports),
            "verified_reports": verified,
            "sources": list(set(r.source_name for r in reports)),
            "date_range": {
                "earliest": min(r.publication_date for r in reports).isoformat(),
                "latest": max(r.publication_date for r in reports).isoformat(),
            },
            "average_confidence": sum(r.match_confidence for r in reports) / len(reports),
            "average_credibility": sum(r.credibility_score for r in reports) / len(reports),
        }

    # =========================================================================
    # EXPORT & IMPORT
    # =========================================================================

    def export_reports(self, case_id: Optional[str] = None) -> List[Dict]:
        """Export reports to dict format."""
        if case_id:
            reports = self.get_case_reports(case_id)
        else:
            reports = list(self.reports.values())
        
        return [
            {
                "report_id": r.report_id,
                "case_id": r.case_id,
                "source_id": r.source_id,
                "source_name": r.source_name,
                "title": r.title,
                "url": r.url,
                "publication_date": r.publication_date.isoformat(),
                "match_confidence": r.match_confidence,
                "credibility_score": r.credibility_score,
                "relevance_level": r.relevance_level.value,
                "verification_status": r.verification_status.value,
                "verified_by": r.verified_by,
                "verification_timestamp": (
                    r.verification_timestamp.isoformat()
                    if r.verification_timestamp else None
                ),
            }
            for r in reports
        ]
