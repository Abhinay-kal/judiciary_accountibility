"""
RTI (Right to Information) Request Generator Package
RTI Act, 2005 - India

Enables citizens to generate, validate, and submit lawful RTI requests
to Public Information Officers across Indian courts.

Modules:
  - templates: Pre-built RTI request templates for common use cases
  - authority_lookup: PIO database and jurisdiction routing
  - validation: Legal compliance and completeness validation
  - generator: Core RTI generation orchestration
  - export: Multi-format export (PDF, docx, text, postal, email)
  - tracking: Request submission tracking and status monitoring
  - personalization: User input collection and privacy controls

Usage Example:
    from app.rti import RTIGenerator, RTIExporter, RTIValidator, RTITracker

    # 1. Create RTI request
    generator = RTIGenerator()
    rti_request = generator.generate(
        request_type="MISSING_RECORDS",
        case_details={"case_number": "123/2023", "court": "District Court"},
        applicant_info={"name": "John Doe", "address": "123 Main St"}
    )

    # 2. Validate compliance
    validator = RTIValidator()
    validation_result = validator.full_validation(rti_request)
    
    # 3. Export to PDF
    exporter = RTIExporter()
    pdf_content = exporter.export_to_pdf(rti_request)

    # 4. Track submission
    tracker = RTITracker()
    request_id = tracker.create_tracking_record(
        request_type="MISSING_RECORDS",
        case_number="123/2023",
        court_name="District Court",
        state="Maharashtra"
    )
"""

__version__ = "1.0.0"
__author__ = "Judiciary Accountability Team"
__license__ = "MIT"

# Core classes
from .templates import (
    RTITemplate,
    RTIRequestType,
    CourtLevel,
    CourtDetails,
    CaseInfo,
    ApplicantInfo,
    RTITemplateLibrary,
)

from .authority_lookup import (
    PIManager,
    PIOMaster,
    CourtLevel,
    State,
)

from .validation import (
    RTIValidator,
    ValidationResult,
)

from .generator import (
    RTIGenerator,
    RTIRequest,
)

from .export import (
    RTIExporter,
    ExportFormat,
)

from .tracking import (
    RTITracker,
    RTITrackingRecord,
    RTIRequestStatus,
    RTIReasonDenial,
)

__all__ = [
    # Templates
    "RTITemplate",
    "RTIRequestType",
    "CourtLevel",
    "CourtDetails",
    "CaseInfo",
    "ApplicantInfo",
    "RTITemplateLibrary",
    
    # Authority Lookup
    "PIManager",
    "PIOMaster",
    "CourtLevel",
    "State",
    
    # Validation
    "RTIValidator",
    "ValidationResult",
    
    # Generator
    "RTIGenerator",
    "RTIRequest",
    
    # Export
    "RTIExporter",
    "ExportFormat",
    
    # Tracking
    "RTITracker",
    "RTITrackingRecord",
    "RTIRequestStatus",
    "RTIReasonDenial",
]
