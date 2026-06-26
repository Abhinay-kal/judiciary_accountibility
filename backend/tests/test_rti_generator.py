"""
Comprehensive RTI Request Generator Test Suite
Tests for templates, validation, generation, export, and tracking
"""

import pytest
from datetime import datetime, timedelta
from app.rti import (
    RTIGenerator,
    RTIValidator,
    RTIExporter,
    RTITracker,
    AuthorityLookup,
    RTIRequestType,
    RTIRequestStatus,
    RTIReasonDenial,
    RTIExportFormat,
    CourtLevel,
)
from app.rti.templates import CaseInfo, ApplicantInfo, CourtDetails, RTITemplate

# =========================================================================
# FIXTURES
# =========================================================================

@pytest.fixture
def rti_generator():
    return RTIGenerator()

@pytest.fixture
def rti_validator():
    return RTIValidator()

@pytest.fixture
def rti_exporter():
    return RTIExporter()

@pytest.fixture
def rti_tracker():
    return RTITracker()

@pytest.fixture
def pio_manager():
    return AuthorityLookup()

@pytest.fixture
def sample_case_info():
    return CaseInfo(
        case_number="123/2023",
        year=2023,
        court_details=CourtDetails(
            name="District Court, Mumbai",
            level=CourtLevel.DISTRICT_COURT,
            state="Maharashtra",
            district="Mumbai"
        )
    )

@pytest.fixture
def sample_applicant_info():
    return ApplicantInfo(
        name="John Doe",
        address_line1="123 Main Street",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        email="john@example.com",
        phone="9876543210"
    )

# =========================================================================
# TESTS: RTI Generator
# =========================================================================

class TestRTIGenerator:
    def test_create_rti_request_success(
        self,
        rti_generator,
        sample_case_info,
        sample_applicant_info
    ):
        success, text, pio_address = rti_generator.create_rti_request(
            request_type=RTIRequestType.MISSING_CASE_RECORDS,
            case_info=sample_case_info,
            applicant_info=sample_applicant_info,
            specific_requests=["Provide certified copy of complete case file"]
        )
        assert success
        assert text is not None
        assert pio_address is not None
        assert "John Doe" in text

    def test_create_rti_request_invalid(
        self,
        rti_generator,
        sample_case_info,
        sample_applicant_info
    ):
        # Empty requests should fail validation
        success, error, pio_address = rti_generator.create_rti_request(
            request_type=RTIRequestType.MISSING_CASE_RECORDS,
            case_info=sample_case_info,
            applicant_info=sample_applicant_info,
            specific_requests=[]
        )
        assert not success
        assert "Validation failed" in error

# =========================================================================
# TESTS: RTI Validation
# =========================================================================

class TestRTIValidation:
    def test_valid_applicant_passes(self, sample_applicant_info):
        is_valid, errors = RTIValidator.validate_applicant_info(sample_applicant_info)
        assert is_valid
        assert len(errors) == 0

    def test_invalid_applicant_fails(self):
        invalid_applicant = ApplicantInfo(
            name="J",  # Too short
            address_line1="123", # Too short
            city="M",
            state="M",
            pincode="400", # Invalid
        )
        is_valid, errors = RTIValidator.validate_applicant_info(invalid_applicant)
        assert not is_valid
        assert len(errors) > 0

    def test_frivolous_request_detection(self):
        requests = ["I think that the judge is corrupt"]
        is_valid, errors = RTIValidator.validate_request_specificity(requests)
        assert not is_valid
        assert len(errors) > 0

    def test_excessive_personal_information_flagged(self):
        requests = ["Provide aadhar 1234-5678-9012 of the witness"]
        is_valid, errors = RTIValidator.validate_no_third_party_pii(requests)
        assert not is_valid
        assert len(errors) > 0

# =========================================================================
# TESTS: RTI Export
# =========================================================================

class TestRTIExport:
    def test_export_to_text(self, rti_exporter):
        success, text_output = rti_exporter.export_rti_request(
            rti_request_text="Sample RTI Body",
            pio_address="PIO, Mumbai",
            applicant_name="John Doe",
            case_number="123/2023",
            export_format=RTIExportFormat.TXT
        )
        assert success
        assert "John Doe" in text_output
        assert "Sample RTI Body" in text_output

    def test_export_to_html(self, rti_exporter):
        success, html_output = rti_exporter.export_rti_request(
            rti_request_text="Sample RTI Body",
            pio_address="PIO, Mumbai",
            applicant_name="John Doe",
            case_number="123/2023",
            export_format=RTIExportFormat.HTML
        )
        assert success
        assert "<html" in html_output

    def test_export_to_postal(self, rti_exporter):
        success, postal_output = rti_exporter.export_rti_request(
            rti_request_text="Sample RTI Body",
            pio_address="PIO, Mumbai",
            applicant_name="John Doe",
            case_number="123/2023",
            export_format=RTIExportFormat.POSTAL
        )
        assert success
        assert "ENVELOPE ADDRESS" in postal_output

# =========================================================================
# TESTS: RTI Tracking
# =========================================================================

class TestRTITracking:
    def test_create_tracking_record(self, rti_tracker):
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="Maharashtra",
            applicant_email="john@example.com",
            applicant_name="John Doe"
        )
        assert request_id is not None
        
        record = rti_tracker.get_request(request_id)
        assert record is not None
        assert record.status == RTIRequestStatus.DRAFT

    def test_mark_submitted(self, rti_tracker):
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="Maharashtra"
        )
        
        success, _ = rti_tracker.mark_submitted(
            request_id=request_id,
            submission_mode="postal",
            submission_reference="POSTAL-123"
        )
        assert success
        record = rti_tracker.get_request(request_id)
        assert record.status == RTIRequestStatus.SUBMITTED

# =========================================================================
# TESTS: Authority Lookup (PIO Manager)
# =========================================================================

class TestAuthorityLookup:
    def test_get_pio_for_district_court(self, pio_manager):
        pio = pio_manager.get_pio_by_court(
            court_level=CourtLevel.DISTRICT_COURT,
            state="Maharashtra",
            district="Mumbai"
        )
        assert pio is not None
        assert pio.court_level == CourtLevel.DISTRICT_COURT
        assert pio.state == "Maharashtra"

    def test_get_pio_for_high_court(self, pio_manager):
        pio = pio_manager.get_pio_by_court(
            court_level=CourtLevel.HIGH_COURT,
            state="Maharashtra"
        )
        assert pio is not None
        assert pio.court_level == CourtLevel.HIGH_COURT

    def test_list_pios_by_state(self, pio_manager):
        pios = pio_manager.search_by_state("mumbai")
        assert len(pios) > 0
        assert all(pio.state == "Maharashtra" for pio in pios)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
