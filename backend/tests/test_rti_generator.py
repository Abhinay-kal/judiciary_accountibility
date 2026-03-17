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
    PIManager,
    RTIRequestType,
    RTIRequestStatus,
    RTIReasonDenial,
    ExportFormat,
    CourtLevel,
    State,
)


# =========================================================================
# FIXTURES
# =========================================================================

@pytest.fixture
def rti_generator():
    """RTI Generator instance."""
    return RTIGenerator()


@pytest.fixture
def rti_validator():
    """RTI Validator instance."""
    return RTIValidator()


@pytest.fixture
def rti_exporter():
    """RTI Exporter instance."""
    return RTIExporter()


@pytest.fixture
def rti_tracker():
    """RTI Tracker instance."""
    return RTITracker()


@pytest.fixture
def pio_manager():
    """PIO Manager instance."""
    return PIManager()


@pytest.fixture
def sample_case_details():
    """Sample case details for testing."""
    return {
        "case_number": "123/2023",
        "case_year": 2023,
        "court_name": "District Court, Mumbai",
        "court_level": "DISTRICT_COURT",
        "state": "maharashtra",
        "judge_name": "Justice Smith",
        "case_status": "pending"
    }


@pytest.fixture
def sample_applicant_info():
    """Sample applicant information for testing."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "9876543210",
        "address": "123 Main Street",
        "city": "Mumbai",
        "state": "maharashtra",
        "pincode": "400001",
        "language": "english"
    }


# =========================================================================
# TESTS: RTI Generator
# =========================================================================

class TestRTIGenerator:
    """Test suite for RTI generation."""

    def test_generate_missing_records_rti(
        self,
        rti_generator,
        sample_case_details,
        sample_applicant_info
    ):
        """Test generation of missing records RTI."""
        rti_request = rti_generator.generate(
            request_type="MISSING_RECORDS",
            case_details=sample_case_details,
            applicant_info=sample_applicant_info
        )
        
        assert rti_request is not None
        assert rti_request.request_type == "MISSING_RECORDS"
        assert rti_request.case_id == "123/2023"
        assert rti_request.applicant == "John Doe"
        assert "@" in rti_request.authority  # PIO email should be present

    def test_generate_transfer_history_rti(
        self,
        rti_generator,
        sample_case_details,
        sample_applicant_info
    ):
        """Test generation of transfer history RTI."""
        rti_request = rti_generator.generate(
            request_type="TRANSFER_HISTORY",
            case_details=sample_case_details,
            applicant_info=sample_applicant_info
        )
        
        assert rti_request.request_type == "TRANSFER_HISTORY"
        assert "transfer" in rti_request.body.lower() or "transfer" in rti_request.subject.lower()

    def test_generate_with_missing_case_details(
        self,
        rti_generator,
        sample_applicant_info
    ):
        """Test that generation handles missing case details gracefully."""
        incomplete_case = {
            "case_number": "123/2023",
            "court_name": "District Court"
            # Missing case_year, state, etc.
        }
        
        # Should still generate but with defaults
        rti_request = rti_generator.generate(
            request_type="MISSING_RECORDS",
            case_details=incomplete_case,
            applicant_info=sample_applicant_info
        )
        
        assert rti_request is not None
        assert rti_request.case_id == "123/2023"


# =========================================================================
# TESTS: RTI Validation
# =========================================================================

class TestRTIValidation:
    """Test suite for RTI validation."""

    def test_valid_rti_passes_validation(
        self,
        rti_validator,
    ):
        """Test that valid RTI passes all validation checks."""
        valid_rti = {
            "body": "I request information about pending orders in case 123/2023",
            "request_type": "PENDING_ORDERS"
        }
        
        result = rti_validator.full_validation(valid_rti)
        
        assert result.is_valid
        assert len(result.errors) == 0

    def test_frivolous_request_detection(
        self,
        rti_validator,
    ):
        """Test that frivolous requests are flagged."""
        frivolous_rti = {
            "body": "I think the judge is dishonest and corrupt",
            "request_type": "MISSING_RECORDS"
        }
        
        result = rti_validator.full_validation(frivolous_rti)
        
        # Should have warnings or fail validation
        assert not result.is_valid or len(result.warnings) > 0

    def test_incomplete_request_detected(
        self,
        rti_validator,
    ):
        """Test detection of incomplete RTI."""
        incomplete_rti = {
            "body": "I want information",
            "request_type": None
        }
        
        result = rti_validator.full_validation(incomplete_rti)
        
        # Should detect incompleteness
        assert not result.is_valid

    def test_excessive_personal_information_flagged(
        self,
        rti_validator,
    ):
        """Test that requests with excessive PII are flagged."""
        excessive_pii_rti = {
            "body": """
            Request regarding John Smith (Aadhar: 1234-5678-9012, 
            phone: 9876543210, address: 123 Main St) and his case
            """,
            "request_type": "CASE_LISTING"
        }
        
        result = rti_validator.full_validation(excessive_pii_rti)
        
        # Should flag PII exposure
        assert len(result.warnings) > 0 or not result.is_valid


# =========================================================================
# TESTS: RTI Export
# =========================================================================

class TestRTIExport:
    """Test suite for RTI export functionality."""

    @pytest.fixture
    def sample_rti_request(self):
        """Sample RTI request for export testing."""
        return {
            "request_type": "MISSING_RECORDS",
            "case_id": "123/2023",
            "authority": "District Collector, Mumbai",
            "subject": "Request for missing court records",
            "body": "I request all missing documents from case 123/2023",
            "declaration": "I hereby declare the above information is correct.",
            "applicant": "John Doe"
        }

    def test_export_to_text(
        self,
        rti_exporter,
        sample_rti_request
    ):
        """Test export to plain text format."""
        text_output = rti_exporter.export_to_text(sample_rti_request)
        
        assert text_output is not None
        assert "John Doe" in text_output
        assert "MISSING_RECORDS" in text_output or "Request" in text_output

    def test_export_to_pdf(
        self,
        rti_exporter,
        sample_rti_request
    ):
        """Test export to PDF format."""
        pdf_output = rti_exporter.export_to_pdf(sample_rti_request)
        
        assert pdf_output is not None
        assert isinstance(pdf_output, (bytes, str))

    def test_export_to_docx(
        self,
        rti_exporter,
        sample_rti_request
    ):
        """Test export to DOCX format."""
        docx_output = rti_exporter.export_to_docx(sample_rti_request)
        
        assert docx_output is not None
        assert isinstance(docx_output, (bytes, str))

    def test_export_to_postal(
        self,
        rti_exporter,
        sample_rti_request
    ):
        """Test export to postal format (print-ready)."""
        postal_output = rti_exporter.export_to_postal(sample_rti_request)
        
        assert postal_output is not None
        # Postal format should include address field placeholders
        assert isinstance(postal_output, (bytes, str))

    def test_export_with_special_characters(
        self,
        rti_exporter
    ):
        """Test export handles special characters correctly."""
        rti_with_special_chars = {
            "request_type": "MISSING_RECORDS",
            "case_id": "123/2023",
            "authority": "District Court, Mumbai (महाराष्ट्र)",
            "subject": "Request for दस्तावेज़",
            "body": "Information needed regarding वर्ष 2023",
            "declaration": "I declare this is true.",
            "applicant": "राज कुमार"
        }
        
        # Should handle non-ASCII characters
        text_output = rti_exporter.export_to_text(rti_with_special_chars)
        assert text_output is not None


# =========================================================================
# TESTS: RTI Tracking
# =========================================================================

class TestRTITracking:
    """Test suite for RTI request tracking."""

    def test_create_tracking_record(
        self,
        rti_tracker
    ):
        """Test creation of tracking record."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra",
            applicant_email="john@example.com",
            applicant_name="John Doe"
        )
        
        assert request_id is not None
        assert len(request_id) > 0
        
        # Should be retrievable
        record = rti_tracker.get_request(request_id)
        assert record is not None
        assert record.request_type == "MISSING_RECORDS"
        assert record.status == RTIRequestStatus.DRAFT

    def test_mark_submitted(
        self,
        rti_tracker
    ):
        """Test marking RTI as submitted."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        success, message = rti_tracker.mark_submitted(
            request_id=request_id,
            submission_mode="postal",
            submission_reference="POSTAL-123-ABC"
        )
        
        assert success
        
        record = rti_tracker.get_request(request_id)
        assert record.status == RTIRequestStatus.SUBMITTED
        assert record.submission_mode == "postal"
        assert record.submission_reference == "POSTAL-123-ABC"

    def test_mark_acknowledged(
        self,
        rti_tracker
    ):
        """Test marking RTI as acknowledged."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        rti_tracker.mark_submitted(request_id, "postal")
        success, _ = rti_tracker.mark_acknowledged(request_id)
        
        assert success
        
        record = rti_tracker.get_request(request_id)
        assert record.status == RTIRequestStatus.ACKNOWLEDGED
        assert record.date_acknowledged is not None

    def test_record_response_received(
        self,
        rti_tracker
    ):
        """Test recording RTI response."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        success, _ = rti_tracker.record_response_received(
            request_id=request_id,
            is_complete=True,
            pages=15
        )
        
        assert success
        
        record = rti_tracker.get_request(request_id)
        assert record.status == RTIRequestStatus.RESPONSE_FULL
        assert record.response_is_complete
        assert record.response_pages == 15

    def test_record_denial(
        self,
        rti_tracker
    ):
        """Test recording RTI denial."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        success, _ = rti_tracker.record_denial(
            request_id=request_id,
            reason=RTIReasonDenial.THIRD_PARTY_PRIVACY,
            denial_text="Information contains third party personal details"
        )
        
        assert success
        
        record = rti_tracker.get_request(request_id)
        assert record.status == RTIRequestStatus.RESPONSE_DENIED
        assert record.denial_reason == RTIReasonDenial.THIRD_PARTY_PRIVACY

    def test_file_appeal(
        self,
        rti_tracker
    ):
        """Test filing appeal against denial."""
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        rti_tracker.record_denial(
            request_id,
            RTIReasonDenial.THIRD_PARTY_PRIVACY,
            "Denied"
        )
        
        success, _ = rti_tracker.file_appeal(
            request_id=request_id,
            appeal_authority="State Information Commission"
        )
        
        assert success
        
        record = rti_tracker.get_request(request_id)
        assert record.appeal_filed
        assert record.status == RTIRequestStatus.APPEAL_FILED

    def test_search_by_case_number(
        self,
        rti_tracker
    ):
        """Test searching RTI by case number."""
        # Create multiple records
        request_id_1 = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra"
        )
        
        request_id_2 = rti_tracker.create_tracking_record(
            request_type="TRANSFER_HISTORY",
            case_number="456/2023",
            case_year=2023,
            court_name="High Court",
            state="maharashtra"
        )
        
        # Search for specific case
        results = rti_tracker.search_by_case("123/2023")
        
        assert len(results) >= 1
        assert results[0].case_number == "123/2023"

    def test_search_by_applicant_email(
        self,
        rti_tracker
    ):
        """Test searching RTI by applicant email."""
        email = "john@example.com"
        
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court, Mumbai",
            state="maharashtra",
            applicant_email=email
        )
        
        results = rti_tracker.search_by_applicant_email(email)
        
        assert len(results) >= 1
        assert results[0].applicant_email == email

    def test_user_statistics(
        self,
        rti_tracker
    ):
        """Test user statistics calculation."""
        email = "john@example.com"
        
        # Create multiple requests
        request_id_1 = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court",
            state="maharashtra",
            applicant_email=email
        )
        
        request_id_2 = rti_tracker.create_tracking_record(
            request_type="TRANSCRIPTS",
            case_number="456/2023",
            case_year=2023,
            court_name="High Court",
            state="maharashtra",
            applicant_email=email
        )
        
        rti_tracker.mark_submitted(request_id_1, "postal")
        rti_tracker.record_response_received(request_id_2)
        
        stats = rti_tracker.get_user_statistics(email)
        
        assert stats["total_requests"] >= 2
        assert stats["submitted"] >= 1
        assert stats["responded"] >= 1

    def test_system_statistics(
        self,
        rti_tracker
    ):
        """Test system-wide statistics."""
        # Create a few requests with different statuses
        request_id_1 = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court",
            state="maharashtra"
        )
        
        request_id_2 = rti_tracker.create_tracking_record(
            request_type="DENIED",
            case_number="456/2023",
            case_year=2023,
            court_name="High Court",
            state="maharashtra"
        )
        
        rti_tracker.mark_submitted(request_id_1, "postal")
        rti_tracker.record_denial(request_id_2, RTIReasonDenial.FRIVOLOUS, "Request too vague")
        
        stats = rti_tracker.get_system_statistics()
        
        assert stats["total_requests"] >= 2
        assert "by_status" in stats
        assert "denial_reasons" in stats

    def test_cleanup_expired_drafts(
        self,
        rti_tracker
    ):
        """Test cleanup of old draft requests."""
        # Create an old draft
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number="123/2023",
            case_year=2023,
            court_name="District Court",
            state="maharashtra"
        )
        
        # Manually age the record
        record = rti_tracker.get_request(request_id)
        record.date_created = datetime.now() - timedelta(days=120)
        
        # Cleanup with 90-day threshold
        deleted_count = rti_tracker.cleanup_expired_drafts(days=90)
        
        assert deleted_count >= 1


# =========================================================================
# TESTS: Authority Lookup (PIO Manager)
# =========================================================================

class TestAuthorityLookup:
    """Test suite for PIO authority lookup."""

    def test_get_pio_for_district_court(
        self,
        pio_manager
    ):
        """Test getting PIO for district court."""
        pio = pio_manager.get_pio_for_court(
            court_level=CourtLevel.DISTRICT_COURT,
            state=State.MAHARASHTRA,
            jurisdiction="Mumbai"
        )
        
        assert pio is not None
        assert pio.court_level == CourtLevel.DISTRICT_COURT
        assert pio.state == State.MAHARASHTRA

    def test_get_pio_for_high_court(
        self,
        pio_manager
    ):
        """Test getting PIO for high court."""
        pio = pio_manager.get_pio_for_court(
            court_level=CourtLevel.HIGH_COURT,
            state=State.MAHARASHTRA
        )
        
        assert pio is not None
        assert pio.court_level == CourtLevel.HIGH_COURT

    def test_get_pio_for_supreme_court(
        self,
        pio_manager
    ):
        """Test getting PIO for supreme court."""
        pio = pio_manager.get_pio_for_court(
            court_level=CourtLevel.SUPREME_COURT,
            state=State.DELHI
        )
        
        assert pio is not None
        assert pio.court_level == CourtLevel.SUPREME_COURT

    def test_list_pios_by_state(
        self,
        pio_manager
    ):
        """Test listing all PIOs in a state."""
        pios = pio_manager.list_pios_by_state(State.MAHARASHTRA)
        
        assert pios is not None
        assert len(pios) > 0
        assert all(pio.state == State.MAHARASHTRA for pio in pios)

    def test_get_pio_address(
        self,
        pio_manager
    ):
        """Test getting formatted PIO address."""
        pio = pio_manager.get_pio_for_court(
            court_level=CourtLevel.DISTRICT_COURT,
            state=State.MAHARASHTRA
        )
        
        if pio:
            address = pio_manager.get_pio_address(pio.pio_id)
            assert address is not None
            assert isinstance(address, str)


# =========================================================================
# INTEGRATION TESTS
# =========================================================================

class TestRTIEndToEnd:
    """End-to-end integration tests."""

    def test_complete_rti_workflow(
        self,
        rti_generator,
        rti_validator,
        rti_exporter,
        rti_tracker,
        sample_case_details,
        sample_applicant_info
    ):
        """Test complete RTI generation workflow."""
        
        # 1. Generate RTI
        rti_request = rti_generator.generate(
            request_type="MISSING_RECORDS",
            case_details=sample_case_details,
            applicant_info=sample_applicant_info
        )
        assert rti_request is not None
        
        # 2. Validate RTI
        validation_result = rti_validator.full_validation(
            {"body": rti_request.body, "request_type": "MISSING_RECORDS"}
        )
        assert validation_result.is_valid
        
        # 3. Create tracking
        request_id = rti_tracker.create_tracking_record(
            request_type="MISSING_RECORDS",
            case_number=sample_case_details["case_number"],
            case_year=sample_case_details["case_year"],
            court_name=sample_case_details["court_name"],
            state=sample_case_details["state"],
            applicant_email=sample_applicant_info["email"],
            applicant_name=sample_applicant_info["name"]
        )
        assert request_id is not None
        
        # 4. Mark as submitted
        rti_tracker.mark_submitted(request_id, "email")
        
        # 5. Export to formats
        text_output = rti_exporter.export_to_text(rti_request.__dict__)
        assert text_output is not None
        
        # 6. Verify tracking
        tracking_record = rti_tracker.get_request(request_id)
        assert tracking_record.status == RTIRequestStatus.SUBMITTED


# =========================================================================
# RUN TESTS
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
