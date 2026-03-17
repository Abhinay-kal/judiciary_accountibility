"""
RTI Request Generator API
FastAPI router for RTI functionality

Endpoints:
  POST /rti/templates - List available RTI templates
  POST /rti/authority/lookup - Find PIO for jurisdiction
  POST /rti/generate - Generate RTI request
  POST /rti/validate - Validate RTI request for compliance
  POST /rti/export - Export RTI to desired format
  POST /rti/track - Create tracking record
  GET /rti/track/{request_id} - Get tracking status
  GET /rti/statistics - Get user/system statistics
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr

from .templates import RTIRequestType, RTI_TEMPLATES
from .authority_lookup import PIManager, CourtLevel, State
from .validation import RTIValidator
from .generator import RTIGenerator, RTIRequest
from .export import RTIExporter, ExportFormat
from .tracking import RTITracker, RTIRequestStatus, RTIReasonDenial


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================

class ApplicantInfoRequest(BaseModel):
    """Applicant information for RTI generation."""
    name: str
    email: EmailStr
    phone: str
    address: str
    city: str
    state: str
    pincode: str
    language: Optional[str] = "english"  # english, hindi, tamil, etc.


class CaseDetailsRequest(BaseModel):
    """Case details for RTI context."""
    case_number: str
    case_year: int
    court_name: str
    court_level: str  # DISTRICT_COURT, HIGH_COURT, SUPREME_COURT
    state: str
    judge_name: Optional[str] = None
    case_status: Optional[str] = None  # pending, disposed, appealed


class TemplateListResponse(BaseModel):
    """Response listing available RTI templates."""
    request_type: str
    description: str
    use_case: str
    sections: List[str]


class PIELookupRequest(BaseModel):
    """Request to lookup PIO for jurisdiction."""
    court_level: str  # DISTRICT_COURT, HIGH_COURT, SUPREME_COURT
    state: str
    jurisdiction: Optional[str] = None


class PIELookupResponse(BaseModel):
    """PIO lookup response."""
    pio_id: str
    pio_name: str
    pio_email: str
    pio_phone: str
    office_address: str
    designation: str
    court_level: str
    state: str


class RTIGenerateRequest(BaseModel):
    """Complete RTI generation request."""
    request_type: str  # from RTIRequestType
    case_details: CaseDetailsRequest
    applicant_info: ApplicantInfoRequest
    information_needs: str  # Description of what information is needed
    urgency: Optional[str] = "regular"  # regular, urgent


class RTIGenerateResponse(BaseModel):
    """Generated RTI request response."""
    request_id: str
    status: str
    request_type: str
    case_number: str
    court_name: str
    state: str
    pio_name: str
    subject_line: str
    body_preview: str
    created_at: datetime


class ValidationRequest(BaseModel):
    """Request to validate RTI for compliance."""
    request_content: str
    request_type: str
    applicant_email: Optional[str] = None


class ValidationResponse(BaseModel):
    """Validation result response."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    compliance_score: float  # 0-100


class ExportRequest(BaseModel):
    """Request to export RTI."""
    request_id: str
    format: str  # pdf, docx, text, postal, email


class ExportResponse(BaseModel):
    """Export result response."""
    success: bool
    format: str
    filename: str
    size_bytes: Optional[int] = None
    download_url: Optional[str] = None


class TrackingCreateRequest(BaseModel):
    """Request to create tracking record."""
    request_type: str
    case_number: str
    case_year: int
    court_name: str
    state: str
    applicant_email: Optional[str] = None
    applicant_name: Optional[str] = None


class TrackingCreateResponse(BaseModel):
    """Tracking record creation response."""
    request_id: str
    status: str
    created_at: datetime


class TrackingSubmitRequest(BaseModel):
    """Request to record submission."""
    request_id: str
    submission_mode: str  # postal, email, online
    submission_reference: Optional[str] = None


class TrackingStatusResponse(BaseModel):
    """Tracking status response."""
    request_id: str
    case_number: str
    court_name: str
    state: str
    status: str
    date_created: datetime
    date_submitted: Optional[datetime] = None
    date_acknowledged: Optional[datetime] = None
    date_responded: Optional[datetime] = None
    response_is_complete: bool = False
    denial_reason: Optional[str] = None
    appeal_filed: bool = False


class StatisticsResponse(BaseModel):
    """Statistics response."""
    total_requests: int
    by_status: dict
    denial_reasons: dict
    appeals_filed: int
    average_response_time_days: Optional[float]


# =========================================================================
# DEPENDENCIES & UTILITIES
# =========================================================================

# Initialize core modules
_rti_generator = RTIGenerator()
_rti_validator = RTIValidator()
_rti_exporter = RTIExporter()
_rti_tracker = RTITracker()
_pio_manager = PIManager()


def get_generator() -> RTIGenerator:
    """Dependency: RTI Generator."""
    return _rti_generator


def get_validator() -> RTIValidator:
    """Dependency: RTI Validator."""
    return _rti_validator


def get_exporter() -> RTIExporter:
    """Dependency: RTI Exporter."""
    return _rti_exporter


def get_tracker() -> RTITracker:
    """Dependency: RTI Tracker."""
    return _rti_tracker


def get_pio_manager() -> PIManager:
    """Dependency: PIO Manager."""
    return _pio_manager


# =========================================================================
# ROUTER DEFINITION
# =========================================================================

router = APIRouter(
    prefix="/rti",
    tags=["RTI"]
)


# =========================================================================
# ENDPOINT: List RTI Templates
# =========================================================================

@router.get("/templates", response_model=List[TemplateListResponse])
async def list_templates():
    """
    Get list of available RTI request templates.
    
    Returns all pre-built RTI templates for common use cases
    (missing records, transfer history, transcripts, etc.)
    """
    templates = []
    
    for request_type, template in RTI_TEMPLATES.items():
        templates.append(
            TemplateListResponse(
                request_type=request_type,
                description=template.description or request_type,
                use_case=getattr(template, 'use_case', 'General RTI request'),
                sections=[
                    "applicant_details",
                    "authority_address",
                    "subject_line",
                    "information_requested",
                    "declaration",
                    "contact_details"
                ]
            )
        )
    
    return templates


# =========================================================================
# ENDPOINT: Lookup PIO
# =========================================================================

@router.post("/authority/lookup", response_model=PIELookupResponse)
async def lookup_pio(
    request: PIELookupRequest,
    pio_manager: PIManager = Depends(get_pio_manager)
):
    """
    Lookup Public Information Officer for given jurisdiction.
    
    Args:
        court_level: DISTRICT_COURT, HIGH_COURT, SUPREME_COURT
        state: Indian state or union territory
        jurisdiction: Optional specific district/circle
    
    Returns:
        PIO contact details and office information
    """
    try:
        pio = pio_manager.get_pio_for_court(
            court_level=CourtLevel[request.court_level.upper()],
            state=State[request.state.upper().replace(" ", "_")],
            jurisdiction=request.jurisdiction
        )
        
        if not pio:
            raise HTTPException(status_code=404, detail="PIO not found for jurisdiction")
        
        return PIELookupResponse(
            pio_id=pio.pio_id,
            pio_name=pio.name,
            pio_email=pio.email,
            pio_phone=pio.phone,
            office_address=pio.office_address,
            designation=pio.designation,
            court_level=pio.court_level.value,
            state=pio.state.value
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Invalid court level or state: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# ENDPOINT: Generate RTI Request
# =========================================================================

@router.post("/generate", response_model=RTIGenerateResponse)
async def generate_rti(
    request: RTIGenerateRequest,
    generator: RTIGenerator = Depends(get_generator),
    tracker: RTITracker = Depends(get_tracker)
):
    """
    Generate RTI request from case details and applicant information.
    
    Args:
        request_type: Type of RTI (MISSING_RECORDS, TRANSFER_HISTORY, etc.)
        case_details: Case number, court, dates, etc.
        applicant_info: Name, email, address, language preference
        information_needs: Description of required information
    
    Returns:
        Generated RTI request details
    """
    try:
        # Convert request objects to dictionaries for generator
        case_dict = request.case_details.dict()
        applicant_dict = request.applicant_info.dict()
        
        # Generate RTI request
        rti_request = generator.generate(
            request_type=request.request_type,
            case_details=case_dict,
            applicant_info=applicant_dict
        )
        
        # Create tracking record
        tracking_id = tracker.create_tracking_record(
            request_type=request.request_type,
            case_number=request.case_details.case_number,
            case_year=request.case_details.case_year,
            court_name=request.case_details.court_name,
            state=request.case_details.state,
            applicant_email=request.applicant_info.email,
            applicant_name=request.applicant_info.name
        )
        
        return RTIGenerateResponse(
            request_id=tracking_id,
            status="draft",
            request_type=request.request_type,
            case_number=request.case_details.case_number,
            court_name=request.case_details.court_name,
            state=request.case_details.state,
            pio_name=rti_request.authority,
            subject_line=rti_request.subject,
            body_preview=rti_request.body[:200] + "..." if len(rti_request.body) > 200 else rti_request.body,
            created_at=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RTI generation failed: {str(e)}")


# =========================================================================
# ENDPOINT: Validate RTI
# =========================================================================

@router.post("/validate", response_model=ValidationResponse)
async def validate_rti(
    request: ValidationRequest,
    validator: RTIValidator = Depends(get_validator)
):
    """
    Validate RTI request for legal compliance and completeness.
    
    Args:
        request_content: RTI request text to validate
        request_type: Type of RTI request
        applicant_email: Applicant email (optional)
    
    Returns:
        Validation result with compliance score and any issues
    """
    try:
        # Create mock RTI object for validation
        rti_mock = {
            "body": request.request_content,
            "request_type": request.request_type
        }
        
        # Run validation
        result = validator.full_validation(rti_mock)
        
        # Calculate compliance score
        max_score = 100
        deductions = len(result.errors) * 10 + len(result.warnings) * 5
        compliance_score = max(0, max_score - deductions)
        
        return ValidationResponse(
            is_valid=result.is_valid,
            errors=result.errors,
            warnings=result.warnings,
            compliance_score=compliance_score
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# =========================================================================
# ENDPOINT: Export RTI
# =========================================================================

@router.post("/export", response_model=ExportResponse)
async def export_rti(
    request: ExportRequest,
    exporter: RTIExporter = Depends(get_exporter),
    tracker: RTITracker = Depends(get_tracker)
):
    """
    Export RTI request to desired format.
    
    Args:
        request_id: Tracking ID of RTI request
        format: pdf, docx, text, postal, or email
    
    Returns:
        Export file details and download URL
    """
    try:
        # Get tracking record
        tracking_record = tracker.get_request(request.request_id)
        if not tracking_record:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Create mock RTI object from tracking record
        rti_mock = {
            "request_type": tracking_record.request_type,
            "case_id": tracking_record.case_number,
            "authority": tracking_record.pio_name or "Public Information Officer",
            "subject": f"RTI Request regarding {tracking_record.court_name}",
            "body": f"Case: {tracking_record.case_number}/{tracking_record.case_year}",
            "declaration": "I hereby declare that above information is correctly stated.",
            "applicant": tracking_record.applicant_name or "Applicant"
        }
        
        # Export to requested format
        format_enum = ExportFormat[request.format.upper()]
        
        if format_enum == ExportFormat.PDF:
            content = exporter.export_to_pdf(rti_mock)
            filename = f"RTI_{tracking_record.case_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
        elif format_enum == ExportFormat.DOCX:
            content = exporter.export_to_docx(rti_mock)
            filename = f"RTI_{tracking_record.case_number}_{datetime.now().strftime('%Y%m%d')}.docx"
        elif format_enum == ExportFormat.TEXT:
            content = exporter.export_to_text(rti_mock)
            filename = f"RTI_{tracking_record.case_number}_{datetime.now().strftime('%Y%m%d')}.txt"
        elif format_enum == ExportFormat.POSTAL:
            content = exporter.export_to_postal(rti_mock)
            filename = f"RTI_{tracking_record.case_number}_POSTAL_{datetime.now().strftime('%Y%m%d')}.pdf"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")
        
        return ExportResponse(
            success=True,
            format=request.format,
            filename=filename,
            size_bytes=len(content) if isinstance(content, bytes) else len(content.encode()),
            download_url=f"/rti/download/{request.request_id}?format={request.format}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# =========================================================================
# ENDPOINT: Create Tracking Record
# =========================================================================

@router.post("/track", response_model=TrackingCreateResponse)
async def create_tracking(
    request: TrackingCreateRequest,
    tracker: RTITracker = Depends(get_tracker)
):
    """
    Create tracking record for RTI request.
    
    Args:
        request_type: Type of RTI request
        case_number: Case number
        case_year: Year of case
        court_name: Court name
        state: Indian state
        applicant_email: Applicant email (optional)
        applicant_name: Applicant name (optional)
    
    Returns:
        Tracking record with unique request_id
    """
    try:
        request_id = tracker.create_tracking_record(
            request_type=request.request_type,
            case_number=request.case_number,
            case_year=request.case_year,
            court_name=request.court_name,
            state=request.state,
            applicant_email=request.applicant_email,
            applicant_name=request.applicant_name
        )
        
        return TrackingCreateResponse(
            request_id=request_id,
            status="draft",
            created_at=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking creation failed: {str(e)}")


# =========================================================================
# ENDPOINT: Get Tracking Status
# =========================================================================

@router.get("/track/{request_id}", response_model=TrackingStatusResponse)
async def get_tracking_status(
    request_id: str,
    tracker: RTITracker = Depends(get_tracker)
):
    """
    Get tracking status and history for RTI request.
    
    Args:
        request_id: Unique RTI request ID
    
    Returns:
        Current status and submission/response timeline
    """
    try:
        tracking_record = tracker.get_request(request_id)
        if not tracking_record:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return TrackingStatusResponse(
            request_id=tracking_record.request_id,
            case_number=tracking_record.case_number,
            court_name=tracking_record.court_name,
            state=tracking_record.state,
            status=tracking_record.status.value,
            date_created=tracking_record.date_created,
            date_submitted=tracking_record.date_submitted,
            date_acknowledged=tracking_record.date_acknowledged,
            date_responded=tracking_record.date_responded,
            response_is_complete=tracking_record.response_is_complete,
            denial_reason=tracking_record.denial_reason.value if tracking_record.denial_reason else None,
            appeal_filed=tracking_record.appeal_filed
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


# =========================================================================
# ENDPOINT: Mark RTI as Submitted
# =========================================================================

@router.post("/track/{request_id}/submit")
async def mark_submitted(
    request_id: str,
    submission: TrackingSubmitRequest,
    tracker: RTITracker = Depends(get_tracker)
):
    """Record that RTI has been submitted."""
    try:
        success, message = tracker.mark_submitted(
            request_id=request_id,
            submission_mode=submission.submission_mode,
            submission_reference=submission.submission_reference
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=message)
        
        return {"success": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Submission recording failed: {str(e)}")


# =========================================================================
# ENDPOINT: Get System Statistics
# =========================================================================

@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    tracker: RTITracker = Depends(get_tracker)
):
    """
    Get system-wide RTI statistics.
    
    Returns:
        Total requests, status breakdown, denial reasons, appeals filed
    """
    try:
        stats = tracker.get_system_statistics()
        
        return StatisticsResponse(
            total_requests=stats["total_requests"],
            by_status=stats["by_status"],
            denial_reasons=stats["denial_reasons"],
            appeals_filed=stats["appeals_filed"],
            average_response_time_days=stats["average_response_time_days"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Statistics retrieval failed: {str(e)}")


# =========================================================================
# HEALTH CHECK
# =========================================================================

@router.get("/health")
async def health_check():
    """RTI service health check."""
    return {
        "status": "healthy",
        "service": "RTI Request Generator",
        "version": "1.0.0"
    }
