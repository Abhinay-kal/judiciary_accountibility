"""
RTI Tracking System
RTI Act, 2005

Tracks RTI request submissions, responses, and appeals.
Provides users with submission history and status monitoring.
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid


class RTIRequestStatus(str, Enum):
    """Status of RTI request."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    UNDER_REVIEW = "under_review"
    RESPONSE_PARTIAL = "response_partial"
    RESPONSE_FULL = "response_full"
    RESPONSE_DENIED = "response_denied"
    APPEAL_FILED = "appeal_filed"
    CLOSED = "closed"
    EXPIRED = "expired"


class RTIReasonDenial(str, Enum):
    """Common reasons for RTI denial under Section 8."""
    NATIONAL_SECURITY = "national_security"
    CABINET_SECRETS = "cabinet_secrets"
    THIRD_PARTY_PRIVACY = "third_party_privacy"
    LEGAL_PROCEEDINGS = "legal_proceedings"
    COMMERCIAL_CONFIDENTIALITY = "commercial_confidentiality"
    PUBLIC_SAFETY = "public_safety"
    FRIVOLOUS = "frivolous"
    VAGUE = "vague"
    DOES_NOT_EXIST = "information_does_not_exist"
    OTHER = "other"


@dataclass
class RTITrackingRecord:
    """Tracking record for individual RTI request."""
    
    request_id: str
    request_type: str
    case_number: str
    case_year: int
    court_name: str
    state: str
    
    applicant_email: Optional[str] = None
    applicant_name: Optional[str] = None
    
    date_created: datetime = None
    date_submitted: Optional[datetime] = None
    date_acknowledged: Optional[datetime] = None
    date_responded: Optional[datetime] = None
    
    status: RTIRequestStatus = RTIRequestStatus.DRAFT
    
    pio_name: Optional[str] = None
    pio_email: Optional[str] = None
    
    submission_mode: Optional[str] = None  # email, postal, online_portal, etc.
    submission_reference: Optional[str] = None  # Postal ref, email tracking, etc.
    
    response_date_received: Optional[datetime] = None
    response_document_id: Optional[str] = None
    response_is_complete: bool = False
    response_pages: int = 0
    
    denial_reason: Optional[RTIReasonDenial] = None
    denial_text: Optional[str] = None
    
    appeal_filed: bool = False
    appeal_authority: Optional[str] = None
    appeal_date: Optional[datetime] = None
    appeal_status: Optional[str] = None
    
    notes: Optional[str] = None
    tags: List[str] = None
    
    date_modified: datetime = None

    def __post_init__(self):
        if self.date_created is None:
            self.date_created = datetime.now()
        if self.date_modified is None:
            self.date_modified = datetime.now()
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "case_number": self.case_number,
            "case_year": self.case_year,
            "court_name": self.court_name,
            "state": self.state,
            "applicant_email": self.applicant_email,
            "applicant_name": self.applicant_name,
            "date_created": self.date_created.isoformat(),
            "date_submitted": self.date_submitted.isoformat() if self.date_submitted else None,
            "date_acknowledged": self.date_acknowledged.isoformat() if self.date_acknowledged else None,
            "date_responded": self.date_responded.isoformat() if self.date_responded else None,
            "status": self.status.value,
            "pio_name": self.pio_name,
            "pio_email": self.pio_email,
            "submission_mode": self.submission_mode,
            "submission_reference": self.submission_reference,
            "response_is_complete": self.response_is_complete,
            "response_pages": self.response_pages,
            "denial_reason": self.denial_reason.value if self.denial_reason else None,
            "denial_text": self.denial_text,
            "appeal_filed": self.appeal_filed,
            "appeal_authority": self.appeal_authority,
            "appeal_date": self.appeal_date.isoformat() if self.appeal_date else None,
            "appeal_status": self.appeal_status,
            "notes": self.notes,
            "tags": self.tags,
            "date_modified": self.date_modified.isoformat(),
        }


class RTITracker:
    """Manages RTI request tracking and status monitoring."""

    def __init__(self):
        # In-memory storage for demo (in production: database)
        self.requests: Dict[str, RTITrackingRecord] = {}

    # =========================================================================
    # CREATE & REGISTER RTI
    # =========================================================================

    def create_tracking_record(
        self,
        request_type: str,
        case_number: str,
        case_year: int,
        court_name: str,
        state: str,
        applicant_email: Optional[str] = None,
        applicant_name: Optional[str] = None,
    ) -> str:
        """
        Create a new RTI tracking record.
        
        Returns:
            request_id (UUID format)
        """
        request_id = str(uuid.uuid4())
        
        record = RTITrackingRecord(
            request_id=request_id,
            request_type=request_type,
            case_number=case_number,
            case_year=case_year,
            court_name=court_name,
            state=state,
            applicant_email=applicant_email,
            applicant_name=applicant_name,
        )
        
        self.requests[request_id] = record
        return request_id

    # =========================================================================
    # UPDATE SUBMISSION STATUS
    # =========================================================================

    def mark_submitted(
        self,
        request_id: str,
        submission_mode: str,
        submission_reference: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Mark RTI as submitted.
        
        Args:
            request_id: Request ID
            submission_mode: 'postal', 'email', 'online', etc.
            submission_reference: Postal ref, email tracking ID, etc.
        """
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.date_submitted = datetime.now()
        record.status = RTIRequestStatus.SUBMITTED
        record.submission_mode = submission_mode
        record.submission_reference = submission_reference
        record.date_modified = datetime.now()
        
        return True, "Submission recorded"

    def mark_acknowledged(self, request_id: str) -> Tuple[bool, str]:
        """Mark RTI as acknowledged by PIO."""
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.date_acknowledged = datetime.now()
        record.status = RTIRequestStatus.ACKNOWLEDGED
        record.date_modified = datetime.now()
        
        return True, "Acknowledgment recorded"

    # =========================================================================
    # RECORD RESPONSE/DENIAL
    # =========================================================================

    def record_response_received(
        self,
        request_id: str,
        is_complete: bool = True,
        pages: int = 0,
    ) -> Tuple[bool, str]:
        """Record that response has been received."""
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.date_responded = datetime.now()
        record.response_date_received = datetime.now()
        record.response_is_complete = is_complete
        record.response_pages = pages
        
        if is_complete:
            record.status = RTIRequestStatus.RESPONSE_FULL
        else:
            record.status = RTIRequestStatus.RESPONSE_PARTIAL
        
        record.date_modified = datetime.now()
        return True, "Response recorded"

    def record_denial(
        self,
        request_id: str,
        reason: RTIReasonDenial,
        denial_text: str,
    ) -> Tuple[bool, str]:
        """Record RTI denial with reason."""
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.date_responded = datetime.now()
        record.status = RTIRequestStatus.RESPONSE_DENIED
        record.denial_reason = reason
        record.denial_text = denial_text
        record.date_modified = datetime.now()
        
        return True, "Denial recorded"

    # =========================================================================
    # APPEAL TRACKING
    # =========================================================================

    def file_appeal(
        self,
        request_id: str,
        appeal_authority: str,
    ) -> Tuple[bool, str]:
        """Record appeal filing against RTI denial."""
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.appeal_filed = True
        record.appeal_authority = appeal_authority
        record.appeal_date = datetime.now()
        record.appeal_status = "filed"
        record.status = RTIRequestStatus.APPEAL_FILED
        record.date_modified = datetime.now()
        
        return True, "Appeal recorded"

    def update_appeal_status(
        self,
        request_id: str,
        new_status: str,
    ) -> Tuple[bool, str]:
        """Update appeal status."""
        if request_id not in self.requests:
            return False, "Request not found"
        
        record = self.requests[request_id]
        record.appeal_status = new_status
        record.date_modified = datetime.now()
        
        return True, "Appeal status updated"

    # =========================================================================
    # RETRIEVAL & SEARCH
    # =========================================================================

    def get_request(self, request_id: str) -> Optional[RTITrackingRecord]:
        """Get tracking record by ID."""
        return self.requests.get(request_id)

    def search_by_case(
        self,
        case_number: str,
        case_year: Optional[int] = None,
    ) -> List[RTITrackingRecord]:
        """Search for RTI requests by case number."""
        results = []
        
        for record in self.requests.values():
            if record.case_number.lower() == case_number.lower():
                if case_year is None or record.case_year == case_year:
                    results.append(record)
        
        return results

    def search_by_applicant_email(
        self,
        email: str,
    ) -> List[RTITrackingRecord]:
        """Search RTI requests by applicant email."""
        return [
            record for record in self.requests.values()
            if record.applicant_email and record.applicant_email.lower() == email.lower()
        ]

    def search_by_status(
        self,
        status: RTIRequestStatus,
    ) -> List[RTITrackingRecord]:
        """Get all requests with specific status."""
        return [
            record for record in self.requests.values()
            if record.status == status
        ]

    def get_pending_acknowledgments(self) -> List[RTITrackingRecord]:
        """Get requests submitted but not yet acknowledged."""
        return [
            record for record in self.requests.values()
            if record.status == RTIRequestStatus.SUBMITTED and
            (datetime.now() - record.date_submitted).days > 5
        ]

    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================

    def get_user_statistics(self, email: str) -> Dict:
        """Get RTI submission statistics for a user."""
        user_requests = self.search_by_applicant_email(email)
        
        return {
            "total_requests": len(user_requests),
            "draft": sum(1 for r in user_requests if r.status == RTIRequestStatus.DRAFT),
            "submitted": sum(1 for r in user_requests if r.status == RTIRequestStatus.SUBMITTED),
            "acknowledged": sum(1 for r in user_requests if r.status == RTIRequestStatus.ACKNOWLEDGED),
            "responded": sum(1 for r in user_requests if r.status in [
                RTIRequestStatus.RESPONSE_FULL,
                RTIRequestStatus.RESPONSE_PARTIAL
            ]),
            "denied": sum(1 for r in user_requests if r.status == RTIRequestStatus.RESPONSE_DENIED),
            "appealed": sum(1 for r in user_requests if r.appeal_filed),
        }

    def get_system_statistics(self) -> Dict:
        """Get system-wide RTI statistics."""
        all_requests = list(self.requests.values())
        
        denied_reasons = {}
        for record in all_requests:
            if record.denial_reason:
                reason_str = record.denial_reason.value
                denied_reasons[reason_str] = denied_reasons.get(reason_str, 0) + 1
        
        return {
            "total_requests": len(all_requests),
            "by_status": {
                status.value: sum(1 for r in all_requests if r.status == status)
                for status in RTIRequestStatus
            },
            "denial_reasons": denied_reasons,
            "appeals_filed": sum(1 for r in all_requests if r.appeal_filed),
            "average_response_time_days": self._calculate_avg_response_time(all_requests),
        }

    @staticmethod
    def _calculate_avg_response_time(records: List[RTITrackingRecord]) -> Optional[float]:
        """Calculate average response time in days."""
        responded = [
            r for r in records
            if r.date_submitted and r.date_responded
        ]
        
        if not responded:
            return None
        
        total_days = sum(
            (r.date_responded - r.date_submitted).days
            for r in responded
        )
        
        return total_days / len(responded)

    # =========================================================================
    # EXPORT & ARCHIVING
    # =========================================================================

    def export_tracking_records(
        self,
        request_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Export tracking records for archival or analysis."""
        if request_ids:
            records = [
                self.requests[rid].to_dict()
                for rid in request_ids
                if rid in self.requests
            ]
        else:
            records = [r.to_dict() for r in self.requests.values()]
        
        return records

    def cleanup_expired_drafts(self, days: int = 90) -> int:
        """Delete draft RTI requests older than specified days."""
        current_time = datetime.now()
        expired_ids = [
            rid for rid, record in self.requests.items()
            if record.status == RTIRequestStatus.DRAFT and
            (current_time - record.date_created).days > days
        ]
        
        for rid in expired_ids:
            del self.requests[rid]
        
        return len(expired_ids)
