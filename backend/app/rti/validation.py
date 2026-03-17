"""
RTI Request Validation
RTI Act, 2005

Validates RTI requests for legal compliance, completeness,
and adherence to RTI Act provisions and court guidelines.
"""

from typing import Tuple, List, Optional
from datetime import datetime
import re
from .templates import (
    RTITemplate, RTIRequestType, CaseInfo, ApplicantInfo, CourtLevel
)


class ValidationError(Exception):
    """Custom exception for RTI validation errors."""
    pass


class RTIValidator:
    """Validates RTI requests for legal and practical compliance."""

    # =========================================================================
    # FIELD VALIDATIONS
    # =========================================================================

    @staticmethod
    def validate_applicant_info(applicant: ApplicantInfo) -> Tuple[bool, List[str]]:
        """
        Validate applicant information completeness.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Name validation
        if not applicant.name or len(applicant.name.strip()) < 2:
            errors.append("Applicant name must be at least 2 characters")

        # Address validation
        if not applicant.address_line1 or len(applicant.address_line1.strip()) < 5:
            errors.append("Address line 1 must be provided (min 5 characters)")

        if not applicant.city or len(applicant.city.strip()) < 2:
            errors.append("City must be provided")

        if not applicant.state or len(applicant.state.strip()) < 2:
            errors.append("State must be provided")

        # Pincode validation (6 digits for Indian pincode)
        if not applicant.pincode or not re.match(r'^\d{6}$', applicant.pincode):
            errors.append("Pincode must be a valid 6-digit Indian postal code")

        # Email validation (if provided)
        if applicant.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, applicant.email):
                errors.append("Invalid email format")

        # Phone validation (if provided)
        if applicant.phone:
            phone_pattern = r'^(\+91)?[6-9]\d{9}$'
            phone_clean = applicant.phone.replace('-', '').replace(' ', '')
            if not re.match(phone_pattern, phone_clean):
                errors.append("Invalid Indian phone number format")

        return len(errors) == 0, errors

    @staticmethod
    def validate_case_info(case_info: CaseInfo) -> Tuple[bool, List[str]]:
        """
        Validate case information for RTI targeting.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Case number validation
        if not case_info.case_number or len(case_info.case_number.strip()) < 2:
            errors.append("Case number must be provided")

        # Year validation
        if not (1900 <= case_info.year <= datetime.now().year):
            errors.append(
                f"Case year must be between 1900 and {datetime.now().year}"
            )

        # Court details validation
        if not case_info.court_details.name:
            errors.append("Court name must be provided")

        if not case_info.court_details.state:
            errors.append("Court state must be provided")

        # Filed date validation (if provided)
        if case_info.filed_date:
            if case_info.filed_date > datetime.now():
                errors.append("Filing date cannot be in the future")
            if case_info.filed_date.year != case_info.year:
                errors.append("Filing date year must match case year")

        return len(errors) == 0, errors

    @staticmethod
    def validate_request_specificity(requests: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that requests are specific and information-seeking,
        not opinion-seeking or frivolous.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        if not requests:
            errors.append("At least one information request must be provided")
            return False, errors

        # Each request should be substantive
        for i, req in enumerate(requests, 1):
            if len(req.strip()) < 10:
                errors.append(
                    f"Request {i}: Request must be at least 10 characters "
                    "(too vague)"
                )

            # Check for opinion-seeking language
            opinion_keywords = [
                "why", "why did", "how could", "should have",
                "could have", "ought to", "was wrong",
                "unfair", "unjust", "opinion", "think that",
            ]
            req_lower = req.lower()
            
            for keyword in opinion_keywords:
                if keyword in req_lower:
                    # Allow "why" if it's asking for documented reasons
                    if keyword != "why" or "reasons for" not in req_lower:
                        errors.append(
                            f"Request {i}: Avoid opinion-seeking language. "
                            f"Request information, not explanations/opinions."
                        )
                        break

        return len(errors) == 0, errors

    @staticmethod
    def validate_no_third_party_pii(requests: List[str]) -> Tuple[bool, List[str]]:
        """
        Check that requests don't ask for personal data of uninvolved third parties.
        RTI Act Section 8(1)(j) exempts personal information.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Patterns for potentially problematic data
        risky_patterns = [
            r'aadhar|aadhaar|ssn|bank account',
            r'salary|income|personal financial',
            r'medical|health|disease',
            r'address.*witness|phone.*witness',
            r'private.*detail|personal.*information',
        ]

        for i, req in enumerate(requests, 1):
            req_lower = req.lower()
            for pattern in risky_patterns:
                if re.search(pattern, req_lower):
                    errors.append(
                        f"Request {i}: May violate privacy of third parties. "
                        f"Avoid requests for personal/financial data of other individuals."
                    )
                    break

        return len(errors) == 0, errors

    @staticmethod
    def validate_jurisdiction_match(
        case_info: CaseInfo,
        authority_level: CourtLevel
    ) -> Tuple[bool, List[str]]:
        """
        Validate that the court level matches the case jurisdiction.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        case_level = case_info.court_details.level
        
        # Case court level should match authority
        if case_level != authority_level:
            errors.append(
                f"Court level mismatch: Case is in {case_level.value} "
                f"but requesting from {authority_level.value}"
            )

        # State match for High Courts
        if authority_level == CourtLevel.HIGH_COURT:
            if case_info.court_details.state.lower() != case_info.court_details.state.lower():
                errors.append(
                    f"State mismatch: Case is in {case_info.court_details.state} "
                    "but requesting from different High Court"
                )

        return len(errors) == 0, errors

    @staticmethod
    def validate_complete_template(template: RTITemplate) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of entire RTI template.
        
        Returns:
            (is_valid, list_of_errors)
        """
        all_errors = []

        # Validate applicant
        applicant_valid, applicant_errors = RTIValidator.validate_applicant_info(
            template.applicant_info
        )
        all_errors.extend(applicant_errors)

        # Validate case
        case_valid, case_errors = RTIValidator.validate_case_info(
            template.case_info
        )
        all_errors.extend(case_errors)

        # Validate requests
        request_valid, request_errors = RTIValidator.validate_request_specificity(
            template.specific_requests
        )
        all_errors.extend(request_errors)

        # Validate privacy
        privacy_valid, privacy_errors = RTIValidator.validate_no_third_party_pii(
            template.specific_requests
        )
        all_errors.extend(privacy_errors)

        # Validate jurisdiction
        jurisdiction_valid, jurisdiction_errors = RTIValidator.validate_jurisdiction_match(
            template.case_info,
            template.case_info.court_details.level
        )
        all_errors.extend(jurisdiction_errors)

        # Declaration must be accepted
        if not template.declaration_accepted:
            all_errors.append(
                "Declaration must be accepted. "
                "You confirm that information provided is true."
            )

        return len(all_errors) == 0, all_errors


class RTIComplianceChecker:
    """Checks RTI request compliance with Act provisions."""

    # RTI Act, 2005 - Key Provisions
    RTI_ACT_PROVISIONS = {
        "section_3": "Right to information",
        "section_4": "Duties of public authorities",
        "section_7": "Request processing timeline (30 days normal, 48 hours urgent)",
        "section_8": "Exemptions (e.g., security, third-party privacy)",
        "section_10": "Fees as per RTI Rules",
        "section_12": "First Appellate Authority",
        "section_19": "Central Information Commission",
    }

    @staticmethod
    def check_for_exempt_information(requests: List[str]) -> List[Dict]:
        """
        Flag potential Section 8 exemptions that PIO may invoke.
        Helps user understand possible denials.
        
        Returns:
            List of potential exemption risks
        """
        risks = []
        
        exempt_patterns = {
            "national_security": r'national|security|defence|armed forces',
            "cabinet_secrets": r'cabinet|minister|internal discussion|policy making',
            "third_party_privacy": r'personal|private|address|phone|financial',
            "legal_proceedings": r'pending|litigation|legal advice|privileged',
            "commercial": r'trade secret|commercial|competitive|proprietary',
            "public_order": r'public order|violence|crime',
        }

        full_request_text = " ".join(requests).lower()

        for exemption_type, pattern in exempt_patterns.items():
            if re.search(pattern, full_request_text):
                risks.append({
                    "exemption": exemption_type,
                    "section": f"Section 8(1) - RTI Act, 2005",
                    "risk_level": "medium",
                    "recommendation": (
                        "This request may be partially or fully denied under "
                        f"Section 8 exemptions. Consider narrowing the scope "
                        "or appealing if denied."
                    )
                })

        return risks

    @staticmethod
    def estimate_processing_time(request_type: RTIRequestType) -> Dict:
        """
        Estimate processing timeline for RTI request.
        
        Per RTI Act, standard timeline is 30 days.
        Complex requests may take longer.
        """
        timelines = {
            RTIRequestType.MISSING_CASE_RECORDS: {
                "standard": 30,
                "complex": 45,
                "expedited": 5,
                "notes": "May require file compilation and certification"
            },
            RTIRequestType.TRANSFER_HISTORY: {
                "standard": 20,
                "complex": 30,
                "expedited": 3,
                "notes": "Court records should have this readily available"
            },
            RTIRequestType.HEARING_TRANSCRIPTS: {
                "standard": 45,
                "complex": 60,
                "expedited": 7,
                "notes": "May depend on availability of recording/stenography"
            },
            RTIRequestType.PENDING_ORDERS_STATUS: {
                "standard": 15,
                "complex": 25,
                "expedited": 2,
                "notes": "Information from case management systems"
            },
            RTIRequestType.CASE_LISTING_DETAILS: {
                "standard": 20,
                "complex": 30,
                "expedited": 3,
                "notes": "Historical cause list information"
            },
            RTIRequestType.ADMINISTRATIVE_DELAYS: {
                "standard": 30,
                "complex": 60,
                "expedited": 5,
                "notes": "Requires case-by-case analysis and compilation"
            },
            RTIRequestType.DATA_DISCREPANCIES: {
                "standard": 30,
                "complex": 45,
                "expedited": 5,
                "notes": "Requires verification and correction process"
            },
            RTIRequestType.CUSTOM: {
                "standard": 30,
                "complex": 60,
                "expedited": 5,
                "notes": "Timeline varies based on request scope"
            }
        }

        return timelines.get(request_type, timelines[RTIRequestType.CUSTOM])

    @staticmethod
    def get_appeal_guidelines() -> Dict:
        """Provide appeal process guidance under RTI Act."""
        return {
            "first_appeal": {
                "authority": "First Appellate Authority (usually senior officer)",
                "timeline": "90 days from appeal receipt",
                "fee": "Same as original RTI fee",
                "grounds": [
                    "Request rejected without valid reason",
                    "Requested period exceeded without response",
                    "Partial disclosure of information",
                    "Information provided is incomplete/inaccurate"
                ]
            },
            "second_appeal": {
                "authority": "Central Information Commission / State Information Commission",
                "timeline": "90 days from appeal receipt",
                "fee": "₹100-500 depending on commission",
                "note": "Only after first appeal exhausted"
            },
            "legal_action": {
                "court": "High Court Writ Jurisdiction",
                "grounds": "Article 226 - Constitutional remedies",
                "timeline": "No statutory limit"
            }
        }
