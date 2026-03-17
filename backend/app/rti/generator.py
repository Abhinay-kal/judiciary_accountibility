"""
RTI Generator - Core RTI Request Generation Logic
RTI Act, 2005

Generates legally compliant RTI applications by combining templates,
case details, applicant information, and validation rules.
"""

from typing import Optional, Tuple, List, Dict
from datetime import datetime
from .templates import (
    RTITemplate, RTIRequestType, CaseInfo, ApplicantInfo, CourtDetails,
    CourtLevel, RTITemplateLibrary
)
from .authority_lookup import AuthorityLookup, PIOMeta
from .validation import RTIValidator, RTIComplianceChecker, ValidationError


class RTIGenerator:
    """Generate complete, validated RTI requests."""

    def __init__(self):
        self.template_library = RTITemplateLibrary()
        self.validator = RTIValidator()
        self.compliance_checker = RTIComplianceChecker()
        self.authority_lookup = AuthorityLookup()

    # =========================================================================
    # TEMPLATE GENERATION
    # =========================================================================

    def generate_rti_text(
        self,
        template: RTITemplate,
        pio: PIOMeta,
        additional_context: Optional[Dict] = None
    ) -> str:
        """
        Generate complete RTI request text by filling template with details.
        
        Args:
            template: RTI template with case and applicant info
            pio: Public Information Officer details
            additional_context: Extra context for specific request types
            
        Returns:
            Complete RTI request text ready for printing/submission
        """
        # Get template text
        template_text = self.template_library.get_template(template.request_type)
        
        # Prepare context dictionary
        context = {
            "pio_name": pio.name,
            "court_name": pio.court_name,
            "court_address": self._format_pio_address(pio),
            "state": pio.state,
            "pincode": pio.pincode,
            "case_number": template.case_info.case_number,
            "case_year": template.case_info.year,
            "applicant_name": template.applicant_info.name,
            "applicant_address": self._format_applicant_address(
                template.applicant_info
            ),
            "applicant_email": template.applicant_info.email or "[Your Email]",
            "applicant_phone": template.applicant_info.phone or "[Your Phone]",
            "from_date": self._format_date(
                template.case_info.filed_date or datetime.now()
            ),
            "language": template.language,
            "date": datetime.now().strftime("%d %B %Y"),
        }

        # Add request-type-specific context
        if template.request_type == RTIRequestType.MISSING_CASE_RECORDS:
            context["from_date"] = self._format_date(
                template.case_info.filed_date or datetime(2010, 1, 1)
            )

        elif template.request_type == RTIRequestType.HEARING_TRANSCRIPTS:
            context["hearing_dates"] = self._format_hearing_dates(
                additional_context.get("hearing_dates", [])
                if additional_context else []
            )

        elif template.request_type == RTIRequestType.DATA_DISCREPANCIES:
            discrepancies = additional_context.get(
                "discrepancy_details", ""
            ) if additional_context else ""
            context["discrepancy_details"] = discrepancies or \
                "[Describe discrepancies found]"

        elif template.request_type == RTIRequestType.CUSTOM:
            custom_req = additional_context.get(
                "custom_request", ""
            ) if additional_context else ""
            context["custom_request"] = custom_req or \
                "[Describe information required]"

        # Fill template
        try:
            generated_text = template_text.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing context key: {e}")

        return generated_text

    # =========================================================================
    # COMPLETE REQUEST GENERATION FLOW
    # =========================================================================

    def create_rti_request(
        self,
        request_type: RTIRequestType,
        case_info: CaseInfo,
        applicant_info: ApplicantInfo,
        specific_requests: List[str],
        additional_context: Optional[Dict] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Main RTI request creation flow with validation.
        
        Args:
            request_type: Type of RTI request
            case_info: Case details for RTI targeting
            applicant_info: RTI applicant information
            specific_requests: List of specific information requests
            additional_context: Additional context (hearing dates, discrepancies, etc.)
            
        Returns:
            (success, generated_text_or_error, pio_address)
        """
        # Step 1: Create template object
        template = RTITemplate(
            request_type=request_type,
            case_info=case_info,
            applicant_info=applicant_info,
            specific_requests=specific_requests,
            declaration_accepted=True,
            language=applicant_info.preferred_language,
        )

        # Step 2: Validate request
        is_valid, errors = RTIValidator.validate_complete_template(template)
        if not is_valid:
            error_msg = "Validation failed:\n" + "\n".join(f"- {e}" for e in errors)
            return False, error_msg, None

        # Step 3: Get correct PIO
        pio = self.authority_lookup.get_pio_by_court(
            court_level=case_info.court_details.level,
            state=case_info.court_details.state,
            district=case_info.court_details.district,
        )
        
        if not pio:
            return False, "Could not identify correct Public Information Officer", None

        # Step 4: Check compliance risks
        exemption_risks = self.compliance_checker.check_for_exempt_information(
            specific_requests
        )

        # Step 5: Generate request text
        try:
            rti_text = self.generate_rti_text(template, pio, additional_context)
        except Exception as e:
            return False, f"Generation error: {str(e)}", None

        # Step 6: Add compliance warnings if needed
        if exemption_risks:
            warnings = "\n\n--- COMPLIANCE WARNINGS ---\n"
            for risk in exemption_risks:
                warnings += f"\n⚠ {risk['exemption'].upper()}\n"
                warnings += f"  Risk: {risk['risk_level']}\n"
                warnings += f"  {risk['recommendation']}\n"
            
            rti_text = warnings + "\n\n--- RTI REQUEST ---\n" + rti_text

        return True, rti_text, self._format_pio_address(pio)

    def batch_create_rti_requests(
        self,
        request_configs: List[Dict]
    ) -> List[Dict]:
        """
        Create multiple RTI requests in batch.
        
        Args:
            request_configs: List of request configurations
            
        Returns:
            List of (success, text, errors) tuples
        """
        results = []
        
        for config in request_configs:
            try:
                success, text, pio_address = self.create_rti_request(
                    request_type=RTIRequestType(config["request_type"]),
                    case_info=config["case_info"],
                    applicant_info=config["applicant_info"],
                    specific_requests=config["specific_requests"],
                    additional_context=config.get("additional_context"),
                )
                
                results.append({
                    "success": success,
                    "text": text if success else None,
                    "error": None if success else text,
                    "pio_address": pio_address,
                    "case_number": config["case_info"].case_number,
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "text": None,
                    "error": str(e),
                    "pio_address": None,
                    "case_number": config.get("case_info", {}).case_number,
                })

        return results

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    @staticmethod
    def _format_pio_address(pio: PIOMeta) -> str:
        """Format PIO address for RTI request."""
        return AuthorityLookup.get_format_address(pio)

    @staticmethod
    def _format_applicant_address(applicant: ApplicantInfo) -> str:
        """Format applicant address for RTI request."""
        address_parts = [
            applicant.address_line1,
        ]
        
        if applicant.address_line2:
            address_parts.append(applicant.address_line2)
        
        address_parts.append(f"{applicant.city}, {applicant.state} {applicant.pincode}")
        
        return ", ".join(address_parts)

    @staticmethod
    def _format_date(date: datetime) -> str:
        """Format date in DD Month YYYY format."""
        return date.strftime("%d %B %Y")

    @staticmethod
    def _format_hearing_dates(dates: List[datetime]) -> str:
        """Format multiple hearing dates."""
        if not dates:
            return "[Specify hearing dates]"
        
        formatted = [d.strftime("%d %B %Y") for d in dates]
        return ", ".join(formatted)

    # =========================================================================
    # TEMPLATE METADATA & GUIDANCE
    # =========================================================================

    def get_available_request_types(self) -> List[Dict]:
        """Get list of supported RTI request types."""
        return self.template_library.list_available_templates()

    def get_processing_timeline(self, request_type: RTIRequestType) -> Dict:
        """Get expected processing timeline for request type."""
        return self.compliance_checker.estimate_processing_time(request_type)

    def get_appeal_info(self) -> Dict:
        """Get appeal process information under RTI Act."""
        return self.compliance_checker.get_appeal_guidelines()

    def get_submission_modes(self) -> List[Dict]:
        """Get acceptable RTI submission modes."""
        return self.authority_lookup.get_submission_modes()

    def get_example_request(self, request_type: RTIRequestType) -> Dict:
        """Get example RTI request for a given type."""
        examples = self.template_library.list_available_templates()
        
        for example in examples:
            if example["type"] == request_type:
                return {
                    "type": example["type"],
                    "title": example["title"],
                    "description": example["description"],
                    "sample_questions": self._get_sample_questions(request_type)
                }
        
        return {}

    @staticmethod
    def _get_sample_questions(request_type: RTIRequestType) -> List[str]:
        """Get sample questions for each request type."""
        samples = {
            RTIRequestType.MISSING_CASE_RECORDS: [
                "Provide certified copy of complete case file",
                "Provide all orders passed since [date]",
                "Provide current status in cause list",
            ],
            RTIRequestType.TRANSFER_HISTORY: [
                "Provide all transfer orders with dates",
                "Provide chronological list of all courts through which case passed",
                "Provide grounds stated for each transfer",
            ],
            RTIRequestType.HEARING_TRANSCRIPTS: [
                "Provide audio recordings of hearings",
                "Provide minutes of proceedings",
                "Provide names of counsel and judges",
            ],
            RTIRequestType.PENDING_ORDERS_STATUS: [
                "Provide list of orders reserved for judgment",
                "Provide date each order was reserved",
                "Provide list of pending applications",
            ],
            RTIRequestType.CASE_LISTING_DETAILS: [
                "Provide copies of all cause lists",
                "Provide dates of all listings",
                "Provide reasons for adjournments",
            ],
            RTIRequestType.ADMINISTRATIVE_DELAYS: [
                "Provide reasons for case pendency",
                "Provide comparison with similar cases",
                "Provide estimated time to disposal",
            ],
            RTIRequestType.DATA_DISCREPANCIES: [
                "Provide verified correct case details",
                "Provide cause of data inconsistencies",
                "Provide timeline of corrections made",
            ],
        }
        
        return samples.get(request_type, [])
