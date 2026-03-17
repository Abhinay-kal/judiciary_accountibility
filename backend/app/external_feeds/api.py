"""
External Feeds API
FastAPI routes for external media coverage integration

Exposes endpoints for viewing, filtering, and verifying external case coverage.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================

class SourceResponse(BaseModel):
    """Source registry entry response."""
    
    source_id: str
    name: str
    organization_type: str
    credibility_score: float
    verification_status: str
    language: str = "en"
    geographic_scope: List[str] = []


class ExternalReportResponse(BaseModel):
    """Single external report response."""
    
    report_id: str
    case_id: str
    source_id: str
    source_name: str
    title: str
    url: str
    publication_date: datetime
    match_confidence: float
    credibility_score: float
    relevance_level: str
    verification_status: str
    summary: Optional[str] = None


class ExternalReportDetailResponse(ExternalReportResponse):
    """Detailed report with summary and facts."""
    
    summary_text: Optional[str] = None
    key_facts: List[str] = []
    verified_by: Optional[str] = None
    verification_timestamp: Optional[datetime] = None


class CaseMediaResponse(BaseModel):
    """Media coverage summary for case."""
    
    case_id: str
    total_reports: int
    verified_reports: int
    external_attention_score: float
    attention_level: str
    sources: List[str]
    date_range: dict
    average_confidence: float
    average_credibility: float
    reports: List[ExternalReportResponse]


class MediaSourcesListResponse(BaseModel):
    """List of available media sources."""
    
    total_sources: int
    sources: List[SourceResponse]
    credibility_score_average: float


class ReportVerificationRequest(BaseModel):
    """Request to verify external report match."""
    
    report_id: str
    verified_by: str
    relevance_level: Optional[str] = None
    notes: Optional[str] = None


class ExternalFeedsAPIRouter:
    """Router for external feeds API endpoints."""

    def __init__(
        self,
        source_registry = None,
        ingestion_pipeline = None,
        matching_engine = None,
        dedup_engine = None,
        credibility_model = None,
        linking_engine = None,
        summarization_engine = None,
    ):
        """
        Initialize router with dependency injection.
        
        Args:
            source_registry: SourceRegistry instance
            ingestion_pipeline: IngestionPipeline instance
            matching_engine: CaseMatchingEngine instance
            dedup_engine: DeduplicationEngine instance
            credibility_model: CredibilityModel instance
            linking_engine: ExternalReportLinkingEngine instance
            summarization_engine: SummarizationEngine instance
        """
        
        self.source_registry = source_registry
        self.ingestion_pipeline = ingestion_pipeline
        self.matching_engine = matching_engine
        self.dedup_engine = dedup_engine
        self.credibility_model = credibility_model
        self.linking_engine = linking_engine
        self.summarization_engine = summarization_engine
        
        self.router = APIRouter(
            prefix="/api/v1/external-feeds",
            tags=["External Feeds"],
        )
        
        self._register_routes()

    # =========================================================================
    # ROUTE REGISTRATION
    # =========================================================================

    def _register_routes(self):
        """Register all API routes."""
        
        # Sources endpoints
        self.router.get("/sources")(self.get_sources)
        self.router.get("/sources/{source_id}")(self.get_source)
        
        # Case media endpoints
        self.router.get("/cases/{case_id}/media")(self.get_case_media)
        self.router.get("/cases/{case_id}/media/summary")(self.get_case_media_summary)
        self.router.get("/cases/{case_id}/attention-score")(self.get_case_attention)
        
        # Report endpoints
        self.router.get("/reports/{report_id}")(self.get_report)
        self.router.get("/reports/{report_id}/summary")(self.get_report_summary)
        
        # Verification endpoints
        self.router.post("/reports/{report_id}/verify")(self.verify_report)
        self.router.post("/reports/{report_id}/dispute")(self.dispute_report)
        
        # Statistics endpoints
        self.router.get("/stats/coverage")(self.get_coverage_stats)
        self.router.get("/stats/credibility")(self.get_credibility_stats)

    # =========================================================================
    # SOURCES ENDPOINTS
    # =========================================================================

    async def get_sources(
        self,
        organization_type: Optional[str] = Query(None),
        verified_only: bool = Query(False),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> MediaSourcesListResponse:
        """
        Get list of media sources.
        
        Query Parameters:
            - organization_type: Filter by MEDIA, NGO, GOVERNMENT, RESEARCH, LEGAL_WATCHDOG
            - verified_only: Show only verified sources
            - limit: Results per page (1-500)
            - offset: Pagination offset
        
        Returns:
            MediaSourcesListResponse
        """
        
        if not self.source_registry:
            raise HTTPException(status_code=503, detail="Source registry unavailable")
        
        # Get all sources
        all_sources = self.source_registry.list_sources()
        
        # Filter by organization type
        if organization_type:
            all_sources = [
                s for s in all_sources
                if s.organization_type.value == organization_type
            ]
        
        # Filter by verification status
        if verified_only:
            all_sources = [
                s for s in all_sources
                if s.verification_status.value == "verified"
            ]
        
        # Apply pagination
        paginated = all_sources[offset:offset + limit]
        
        # Convert to response models
        sources_response = [
            SourceResponse(
                source_id=s.source_id,
                name=s.name,
                organization_type=s.organization_type.value,
                credibility_score=self.source_registry.get_credibility_score(s.source_id),
                verification_status=s.verification_status.value,
                language=s.language,
                geographic_scope=s.geographic_scope,
            )
            for s in paginated
        ]
        
        # Calculate average credibility
        avg_credibility = (
            sum(s.credibility_score for s in sources_response) / len(sources_response)
            if sources_response else 0.0
        )
        
        return MediaSourcesListResponse(
            total_sources=len(all_sources),
            sources=sources_response,
            credibility_score_average=round(avg_credibility, 3),
        )

    async def get_source(self, source_id: str) -> SourceResponse:
        """Get single source by ID."""
        
        if not self.source_registry:
            raise HTTPException(status_code=503, detail="Source registry unavailable")
        
        source = self.source_registry.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        return SourceResponse(
            source_id=source.source_id,
            name=source.name,
            organization_type=source.organization_type.value,
            credibility_score=self.source_registry.get_credibility_score(source_id),
            verification_status=source.verification_status.value,
            language=source.language,
            geographic_scope=source.geographic_scope,
        )

    # =========================================================================
    # CASE MEDIA ENDPOINTS
    # =========================================================================

    async def get_case_media(
        self,
        case_id: str,
        verified_only: bool = Query(False),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> CaseMediaResponse:
        """
        Get external media coverage for case.
        
        Query Parameters:
            - verified_only: Show only manually verified matches
            - limit: Results per page
            - offset: Pagination offset
        
        Returns:
            CaseMediaResponse with articles and statistics
        """
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        # Get case reports
        all_reports = self.linking_engine.get_case_reports(case_id)
        
        if not all_reports:
            raise HTTPException(status_code=404, detail="No media coverage found for case")
        
        # Filter by verification status
        if verified_only:
            all_reports = [
                r for r in all_reports
                if r.verification_status.value == "manually_verified"
            ]
        
        # Apply pagination
        paginated = all_reports[offset:offset + limit]
        
        # Convert to response models
        reports = [
            ExternalReportResponse(
                report_id=r.report_id,
                case_id=r.case_id,
                source_id=r.source_id,
                source_name=r.source_name,
                title=r.title,
                url=r.url,
                publication_date=r.publication_date,
                match_confidence=r.match_confidence,
                credibility_score=r.credibility_score,
                relevance_level=r.relevance_level.value if hasattr(r.relevance_level, 'value') else r.relevance_level,
                verification_status=r.verification_status.value,
                summary=r.summary,
            )
            for r in paginated
        ]
        
        # Get case summary
        case_summary = self.linking_engine.get_case_report_summary(case_id)
        
        # Get attention score
        attention_score = self.credibility_model.get_attention_score(case_id) if self.credibility_model else None
        attention_level = attention_score.attention_level.value if attention_score else "unknown"
        attention_score_value = attention_score.score if attention_score else 0.0
        
        return CaseMediaResponse(
            case_id=case_id,
            total_reports=case_summary.get("total_reports", 0),
            verified_reports=case_summary.get("verified_reports", 0),
            external_attention_score=attention_score_value,
            attention_level=attention_level,
            sources=case_summary.get("sources", []),
            date_range=case_summary.get("date_range", {}),
            average_confidence=case_summary.get("average_confidence", 0.0),
            average_credibility=case_summary.get("average_credibility", 0.0),
            reports=reports,
        )

    async def get_case_media_summary(self, case_id: str) -> dict:
        """Get high-level summary of case media coverage."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        summary = self.linking_engine.get_case_report_summary(case_id)
        
        if summary.get("total_reports") == 0:
            raise HTTPException(status_code=404, detail="No media coverage found")
        
        return summary

    async def get_case_attention(self, case_id: str) -> dict:
        """Get external attention score for case."""
        
        if not self.credibility_model:
            raise HTTPException(status_code=503, detail="Credibility model unavailable")
        
        score = self.credibility_model.get_attention_score(case_id)
        
        if not score:
            raise HTTPException(status_code=404, detail="No attention score calculated")
        
        return {
            "case_id": case_id,
            "attention_score": round(score.score, 3),
            "attention_level": score.attention_level.value,
            "total_articles": score.total_articles,
            "credible_sources": score.credible_source_count,
            "coverage_span_days": score.coverage_span_days,
            "most_recent_coverage": (
                score.most_recent_coverage_date.isoformat()
                if score.most_recent_coverage_date else None
            ),
        }

    # =========================================================================
    # REPORT ENDPOINTS
    # =========================================================================

    async def get_report(self, report_id: str) -> ExternalReportResponse:
        """Get single report details."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        report = self.linking_engine.get_report(report_id)
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return ExternalReportResponse(
            report_id=report.report_id,
            case_id=report.case_id,
            source_id=report.source_id,
            source_name=report.source_name,
            title=report.title,
            url=report.url,
            publication_date=report.publication_date,
            match_confidence=report.match_confidence,
            credibility_score=report.credibility_score,
            relevance_level=report.relevance_level.value if hasattr(report.relevance_level, 'value') else report.relevance_level,
            verification_status=report.verification_status.value,
            summary=report.summary,
        )

    async def get_report_summary(
        self,
        report_id: str,
    ) -> ExternalReportDetailResponse:
        """Get report with generated summary."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        report = self.linking_engine.get_report(report_id)
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Get generated summary if available
        summary_obj = None
        if self.summarization_engine:
            summary_obj = self.summarization_engine.get_summary(report_id)
        
        return ExternalReportDetailResponse(
            report_id=report.report_id,
            case_id=report.case_id,
            source_id=report.source_id,
            source_name=report.source_name,
            title=report.title,
            url=report.url,
            publication_date=report.publication_date,
            match_confidence=report.match_confidence,
            credibility_score=report.credibility_score,
            relevance_level=report.relevance_level.value if hasattr(report.relevance_level, 'value') else report.relevance_level,
            verification_status=report.verification_status.value,
            summary=report.summary,
            summary_text=summary_obj.summary_text if summary_obj else None,
            key_facts=summary_obj.key_facts if summary_obj else [],
            verified_by=report.verified_by,
            verification_timestamp=report.verification_timestamp,
        )

    # =========================================================================
    # VERIFICATION ENDPOINTS
    # =========================================================================

    async def verify_report(
        self,
        report_id: str,
        request: ReportVerificationRequest,
    ) -> dict:
        """Manually verify external report match."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        success = self.linking_engine.verify_report(
            report_id=report_id,
            verified_by=request.verified_by,
            relevance_level=request.relevance_level,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {
            "success": True,
            "report_id": report_id,
            "verification_status": "manually_verified",
            "verified_by": request.verified_by,
            "verified_at": datetime.now().isoformat(),
        }

    async def dispute_report(self, report_id: str) -> dict:
        """Mark report as disputed/false positive."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        success = self.linking_engine.dispute_report(report_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return {
            "success": True,
            "report_id": report_id,
            "verification_status": "disputed",
        }

    # =========================================================================
    # STATISTICS ENDPOINTS
    # =========================================================================

    async def get_coverage_stats(self) -> dict:
        """Get overall coverage statistics."""
        
        if not self.linking_engine:
            raise HTTPException(status_code=503, detail="Linking engine unavailable")
        
        stats = self.linking_engine.get_linking_stats()
        
        return {
            "total_reports": stats.get("total_reports", 0),
            "cases_with_coverage": stats.get("cases_with_reports", 0),
            "sources_represented": stats.get("sources_represented", 0),
            "verification_breakdown": stats.get("verification_counts", {}),
            "relevance_breakdown": stats.get("relevance_counts", {}),
            "average_match_confidence": round(stats.get("average_confidence", 0.0), 3),
        }

    async def get_credibility_stats(self) -> dict:
        """Get credibility assessment statistics."""
        
        if not self.credibility_model:
            raise HTTPException(status_code=503, detail="Credibility model unavailable")
        
        stats = self.credibility_model.get_credibility_stats()
        
        return {
            "cases_with_coverage": stats.get("cases_with_coverage", 0),
            "total_articles": stats.get("total_articles", 0),
            "average_attention_score": round(stats.get("average_attention_score", 0.0), 3),
            "by_attention_level": stats.get("by_attention_level", {}),
            "high_attention_cases": stats.get("high_attention_cases", 0),
        }

    def get_router(self) -> APIRouter:
        """Get configured APIRouter instance."""
        return self.router
