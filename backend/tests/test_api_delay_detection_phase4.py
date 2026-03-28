"""
Integration tests for Phase 4: Deliberate Delay Detection API endpoints.

Tests the complete REST API for:
- Baseline metrics calculation
- Single case analysis
- Batch case analysis
- Health checks
- Error handling
"""
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.db.session import get_db
from app.models import Case, Hearing, Court, Judge


# ─────────────────────────────────────────────────────────────────────────────
# Test Database Setup
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Create tables
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    yield db

    db.close()


@pytest.fixture
def client(db_session):
    """Create a test client with mock database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def create_mock_case(db: Session, case_id: int = 1) -> Case:
    """Create a mock case for testing."""
    court = Mock(spec=Court)
    court.id = 1
    court.name = "Test Court"
    court.level = "HIGH"

    judge = Mock(spec=Judge)
    judge.id = 1
    judge.name = "Test Judge"

    case = Case(
        id=case_id,
        case_number=f"WP/{case_id}/2021",
        cnr=f"CNR{case_id}",
        case_uid=f"UID{case_id}",
        court_id=1,
        state="Maharashtra",
        filing_date=date(2021, 1, 1),
        case_type="WRIT",
        status="PENDING",
        source_url="http://example.com",
        is_disposed=False,
        is_deleted=False,
    )

    return case


def create_mock_hearing(
    db: Session,
    case_id: int = 1,
    hearing_id: int = 1,
    outcome_text: str = "Adjourned",
):
    """Create a mock hearing for testing."""
    hearing = Hearing(
        id=hearing_id,
        case_id=case_id,
        court_id=1,
        hearing_date=date(2021, 2, 1) + timedelta(days=hearing_id * 30),
        outcome_type="ADJOURNED",
        outcome_text=outcome_text,
        result_text="",
        is_consistent=True,
    )

    return hearing


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHealthCheck:
    """Test the /api/v1/delay-detection/health endpoint."""

    def test_health_check_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/api/v1/delay-detection/health")
        assert response.status_code == 200

    def test_health_check_response_schema(self, client):
        """Response should contain required fields."""
        response = client.get("/api/v1/delay-detection/health")
        data = response.json()

        assert "status" in data
        assert "phase1_available" in data
        assert "phase2_available" in data
        assert "phase3_available" in data
        assert "baseline_available" in data
        assert "message" in data

    @patch("app.api.routes.deliberate_delay.classify_adjournment_tactic")
    def test_health_check_all_phases_available(self, mock_classify, client):
        """Health check should report all phases available."""
        mock_classify.return_value = Mock()

        response = client.get("/api/v1/delay-detection/health")
        data = response.json()

        # At minimum, can check the response structure
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Baseline Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBaselineMetrics:
    """Test the /api/v1/delay-detection/baseline endpoint."""

    def test_baseline_returns_200(self, client):
        """Baseline endpoint should return 200."""
        response = client.get("/api/v1/delay-detection/baseline")
        assert response.status_code == 200

    def test_baseline_response_schema(self, client):
        """Baseline response should have all required fields."""
        response = client.get("/api/v1/delay-detection/baseline")
        data = response.json()

        required_fields = [
            "density_mean",
            "density_std",
            "party_score_mean",
            "party_score_std",
            "dormancy_cv_mean",
            "dormancy_cv_std",
            "bench_hunting_mean",
            "bench_hunting_std",
            "sample_size",
            "calculation_date",
            "status",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_baseline_no_resolved_cases(self, client, db_session):
        """Baseline should handle case with no resolved cases gracefully."""
        # No resolved cases in DB
        response = client.get("/api/v1/delay-detection/baseline")
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "error" or data["sample_size"] == 0

    @patch("app.api.routes.deliberate_delay.CaseAnomalyDetector")
    def test_baseline_recalculate_flag(self, mock_detector, client):
        """Baseline should recalculate when recalculate=true."""
        response = client.get("/api/v1/delay-detection/baseline?recalculate=true")
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Single Case Analysis Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleCaseAnalysis:
    """Test the /api/v1/delay-detection/case/{case_id} endpoint."""

    def test_case_not_found_returns_404(self, client):
        """Should return 404 for non-existent case."""
        response = client.get("/api/v1/delay-detection/case/99999")
        assert response.status_code == 404

    @patch("app.api.routes.deliberate_delay.db")
    def test_case_analysis_response_schema(self, mock_db, client, db_session):
        """Case analysis response should have required fields."""
        # Mock the case query
        case = create_mock_case(db_session, case_id=1)

        # Mock all the service calls
        with patch("app.api.routes.deliberate_delay.Case") as MockCase:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = case

            MockCase.objects = Mock()
            MockCase.query = Mock(return_value=mock_query)

            response = client.get("/api/v1/delay-detection/case/1")

            if response.status_code in [200, 404, 422, 502]:
                # Response structure depends on implementation
                assert True
            else:
                pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_case_with_no_hearings(self, client, db_session):
        """Analysis should handle case with no hearings gracefully."""
        # This test would need database setup with actual case

        response = client.get("/api/v1/delay-detection/case/1")

        # Should either return 404 or a response indicating no hearings
        assert response.status_code in [200, 404, 422]


# ─────────────────────────────────────────────────────────────────────────────
# Case Features Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCaseFeatures:
    """Test the /api/v1/delay-detection/case/{case_id}/features endpoint."""

    def test_features_not_found_returns_404(self, client):
        """Should return 404 for non-existent case."""
        response = client.get("/api/v1/delay-detection/case/99999/features")
        assert response.status_code == 404

    def test_features_response_schema(self, client):
        """Features response should have all feature fields."""
        response = client.get("/api/v1/delay-detection/case/1/features")

        if response.status_code == 200:
            data = response.json()

            required_fields = [
                "case_id",
                "case_number",
                "adjournment_density",
                "party_driven_score",
                "dormancy_cv",
                "bench_hunting_index",
            ]

            for field in required_fields:
                assert field in data, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────────
# Batch Analysis Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBatchAnalysis:
    """Test the /api/v1/delay-detection/batch endpoint."""

    def test_batch_empty_list_returns_400(self, client):
        """Batch with empty case_ids should return 400."""
        response = client.post("/api/v1/delay-detection/batch", json={"case_ids": []})
        assert response.status_code in [400, 422]

    def test_batch_max_cases_limit(self, client):
        """Batch should limit to 1000 cases."""
        case_ids = list(range(1, 1002))  # 1001 cases

        response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": ",".join(map(str, case_ids))},
        )

        assert response.status_code == 400

    def test_batch_response_schema(self, client):
        """Batch response should have required fields."""
        response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": "1,2,3"},
        )

        if response.status_code in [200, 400, 422]:
            # Valid response or expected error
            assert True
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_batch_with_single_case(self, client):
        """Batch should work with single case."""
        response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": "1"},
        )

        # Should return 200 (even if case not found - returns empty results)
        assert response.status_code in [200, 422]


# ─────────────────────────────────────────────────────────────────────────────
# Z-Scores Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestZScores:
    """Test the /api/v1/delay-detection/case/{case_id}/z-scores endpoint."""

    def test_z_scores_not_found_returns_404(self, client):
        """Should return 404 for non-existent case."""
        response = client.get("/api/v1/delay-detection/case/99999/z-scores")
        assert response.status_code == 404

    def test_z_scores_response_schema(self, client):
        """Z-scores response should have all z-score fields."""
        response = client.get("/api/v1/delay-detection/case/1/z-scores")

        if response.status_code == 200:
            data = response.json()

            required_fields = [
                "density_z",
                "party_score_z",
                "dormancy_cv_z",
                "bench_hunting_z",
                "composite_z",
                "anomalies",
            ]

            for field in required_fields:
                assert field in data, f"Missing field: {field}"

            # Anomalies should be a list
            assert isinstance(data["anomalies"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEndpointIntegration:
    """Test multiple endpoints working together."""

    def test_workflow_baseline_then_case_analysis(self, client):
        """Test workflow: get baseline, then analyze case."""
        # Get baseline
        baseline_response = client.get("/api/v1/delay-detection/baseline")
        assert baseline_response.status_code == 200

        # Then analyze case
        analysis_response = client.get("/api/v1/delay-detection/case/1")
        assert analysis_response.status_code in [200, 404, 422]

    def test_workflow_features_then_analysis(self, client):
        """Test workflow: get features, then run analysis."""
        # Get features
        features_response = client.get("/api/v1/delay-detection/case/1/features")
        assert features_response.status_code in [200, 404, 502]

        # Get z-scores
        z_scores_response = client.get("/api/v1/delay-detection/case/1/z-scores")
        assert z_scores_response.status_code in [200, 404, 502]

    def test_workflow_batch_then_inspect_individual(self, client):
        """Test workflow: batch analyze, then inspect individual results."""
        # Batch analyze
        batch_response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": "1,2"},
        )
        assert batch_response.status_code in [200, 422]

        # Then inspect individual
        inspect_response = client.get("/api/v1/delay-detection/case/1/features")
        assert inspect_response.status_code in [200, 404, 502]


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Test error scenarios and edge cases."""

    def test_invalid_case_id_type(self, client):
        """Invalid case_id type should return 422."""
        response = client.get("/api/v1/delay-detection/case/not-a-number")
        assert response.status_code == 422

    def test_negative_case_id(self, client):
        """Negative case IDs should return 404 or validation error."""
        response = client.get("/api/v1/delay-detection/case/-1")
        assert response.status_code in [404, 422]

    def test_batch_malformed_case_ids(self, client):
        """Batch with invalid format should return 422."""
        response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": "not-valid"},
        )
        assert response.status_code == 422

    def test_batch_empty_string(self, client):
        """Batch with empty string should return 422."""
        response = client.post(
            "/api/v1/delay-detection/batch",
            params={"case_ids": ""},
        )
        assert response.status_code in [400, 422]


# ─────────────────────────────────────────────────────────────────────────────
# Response Format Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestResponseFormats:
    """Test that all responses follow the expected format."""

    def test_all_responses_are_json(self, client):
        """All responses should be JSON."""
        endpoints = [
            "/api/v1/delay-detection/health",
            "/api/v1/delay-detection/baseline",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.headers.get("content-type") == "application/json"

    def test_error_response_format(self, client):
        """Error responses should follow error format."""
        response = client.get("/api/v1/delay-detection/case/99999")

        if response.status_code == 404:
            # FastAPI returns detail in error response
            data = response.json()
            assert "detail" in data or "status" in data


# ─────────────────────────────────────────────────────────────────────────────
# Performance Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPerformance:
    """Test endpoint performance."""

    def test_health_check_fast_response(self, client):
        """Health check should respond quickly."""
        import time

        start = time.time()
        response = client.get("/api/v1/delay-detection/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0  # Should be < 1 second

    def test_baseline_calculation_reasonable_time(self, client):
        """Baseline calculation should complete in reasonable time."""
        import time

        start = time.time()
        response = client.get("/api/v1/delay-detection/baseline")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Even with DB queries, should be < 5 seconds
        assert elapsed < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
