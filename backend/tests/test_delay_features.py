"""
Comprehensive tests for Phase 2 Delay Feature Engineering.

Tests all 4 features:
1. Adjournment Density
2. Party-Driven Delay Score
3. Dormancy Variance
4. Bench Hunting Index
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, Mock

from sqlalchemy.orm import Session

from app.models import (
    Case,
    Adjournment,
    Hearing,
    HearingOutcomeType,
    PublicStatus,
)
from app.models.entities import AdjournmentReasonType
from app.schemas.delay_features import (
    BenchHuntingLevel,
    DelayScoreLevel,
)
from app.services.delay_features import DelayFeatureExtractor


@pytest.fixture
def db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    session.query = MagicMock()
    session.execute = MagicMock()
    return session


@pytest.fixture
def extractor(db_session):
    """Create feature extractor with mocked session."""
    return DelayFeatureExtractor(db_session)


class TestAdjournmentDensity:
    """Tests for adjournment density calculation."""

    def test_density_zero_adjournments(self, extractor, db_session):
        """Test case with no adjournments."""
        case = MagicMock(spec=Case)
        case.id = 1

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            5,  # total_hearings = 5
            0,  # total_adjournments = 0
        ]

        density = extractor.extract_adjournment_density(1)

        assert density.case_id == 1
        assert density.total_hearings == 5
        assert density.total_adjournments == 0
        assert density.density_percentage == 0.0
        assert not density.is_outlier

    def test_density_all_adjourned(self, extractor, db_session):
        """Test case where all hearings were adjourned."""
        case = MagicMock(spec=Case)
        case.id = 2

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            10,  # total_hearings = 10
            10,  # total_adjournments = 10
        ]

        density = extractor.extract_adjournment_density(2, population_mean=30.0, population_std_dev=10.0)

        assert density.case_id == 2
        assert density.total_hearings == 10
        assert density.total_adjournments == 10
        assert density.density_percentage == 100.0
        assert density.is_outlier  # 100% > 30 + 2*10

    def test_density_partial_adjournments(self, extractor, db_session):
        """Test case with partial adjournments."""
        case = MagicMock(spec=Case)
        case.id = 3

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.scalar.side_effect = [
            20,  # total_hearings
            5,  # total_adjournments
        ]

        density = extractor.extract_adjournment_density(3, population_mean=25.0, population_std_dev=5.0)

        assert density.density_percentage == 25.0
        assert not density.is_outlier  # 25% <= 25 + 2*5


class TestPartyDrivenDelay:
    """Tests for party-driven delay scoring."""

    def test_no_adjournments(self, extractor, db_session):
        """Test case with no adjournments."""
        case = MagicMock(spec=Case)
        case.id = 1

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = extractor.extract_party_driven_delay(1)

        assert result.case_id == 1
        assert result.total_adjournments == 0
        assert result.party_requested_adjournments == 0
        assert result.party_request_percentage == 0.0
        assert result.level == DelayScoreLevel.LOW

    def test_all_party_requested(self, extractor, db_session):
        """Test case where all adjournments were party-requested."""
        case = MagicMock(spec=Case)
        case.id = 2

        adj1 = MagicMock(spec=Adjournment)
        adj1.reason_type = AdjournmentReasonType.ON_REQUEST
        adj1.requested_by = 1

        adj2 = MagicMock(spec=Adjournment)
        adj2.reason_type = AdjournmentReasonType.ON_REQUEST
        adj2.requested_by = 1

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.all.return_value = [adj1, adj2]

        result = extractor.extract_party_driven_delay(2)

        assert result.total_adjournments == 2
        assert result.party_requested_adjournments == 2
        assert result.party_request_percentage == 100.0
        assert result.level == DelayScoreLevel.EXTREME

    def test_mixed_party_court_requests(self, extractor, db_session):
        """Test case with both party and court-requested adjournments."""
        case = MagicMock(spec=Case)
        case.id = 3

        adj_party = MagicMock(spec=Adjournment)
        adj_party.reason_type = AdjournmentReasonType.ON_REQUEST
        adj_party.requested_by = 2

        adj_court = MagicMock(spec=Adjournment)
        adj_court.reason_type = AdjournmentReasonType.JUDGE_UNAVAILABLE
        adj_court.requested_by = None

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.all.return_value = [adj_party, adj_court]

        result = extractor.extract_party_driven_delay(3)

        assert result.total_adjournments == 2
        assert result.party_requested_adjournments == 1
        assert result.party_request_percentage == 50.0
        assert result.level == DelayScoreLevel.MODERATE


class TestDormancyVariance:
    """Tests for dormancy variance calculation."""

    def test_no_hearings(self, extractor, db_session):
        """Test case with no hearings."""
        case = MagicMock(spec=Case)
        case.id = 1

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = extractor.extract_dormancy_variance(1, population_median_cv=0.5)

        assert result.case_id == 1
        assert result.hearing_gaps_days == []
        assert result.min_gap_days == 0
        assert result.max_gap_days == 0
        assert result.variance == 0.0
        assert not result.is_irregular_pattern

    def test_uniform_hearing_gaps(self, extractor, db_session):
        """Test case with uniform gaps between hearings."""
        case = MagicMock(spec=Case)
        case.id = 2

        # Create dates with 30-day gaps
        dates = [
            (date(2024, 1, 1),),
            (date(2024, 1, 31),),
            (date(2024, 3, 2),),
            (date(2024, 4, 1),),
        ]

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = dates

        result = extractor.extract_dormancy_variance(2, population_median_cv=0.5)

        assert result.case_id == 2
        assert len(result.hearing_gaps_days) == 3
        assert result.coefficient_of_variation < 0.2  # Low variance for uniform gaps
        assert not result.is_irregular_pattern

    def test_irregular_hearing_gaps(self, extractor, db_session):
        """Test case with irregular gaps (indicating deliberate delays)."""
        case = MagicMock(spec=Case)
        case.id = 3

        # Create dates with highly variable gaps: 5, 90, 2, 120 days
        dates = [
            (date(2024, 1, 1),),
            (date(2024, 1, 6),),
            (date(2024, 4, 5),),
            (date(2024, 4, 7),),
            (date(2024, 8, 5),),
        ]

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = dates

        result = extractor.extract_dormancy_variance(3, population_median_cv=0.3)

        assert result.case_id == 3
        assert len(result.hearing_gaps_days) == 4
        assert result.coefficient_of_variation > 0.5  # High variance for irregular gaps
        assert result.is_irregular_pattern


class TestBenchHunting:
    """Tests for bench hunting index calculation."""

    def test_single_court_no_bench_changes(self, extractor, db_session):
        """Test case with single court and no bench changes."""
        case = MagicMock(spec=Case)
        case.id = 1
        case.court_id = 10

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.count.return_value = 1
        db_session.query.return_value.order_by.return_value.all.return_value = [
            (5,),  # judge_id = 5
            (5,),  # judge_id = 5
            (5,),  # judge_id = 5
        ]

        result = extractor.extract_bench_hunting(1)

        assert result.case_id == 1
        assert result.hunting_index == 0.0
        assert result.level == BenchHuntingLevel.NO_HUNTING
        assert result.bench_changes == 0

    def test_multiple_bench_changes(self, extractor, db_session):
        """Test case with frequent bench changes."""
        case = MagicMock(spec=Case)
        case.id = 2
        case.court_id = 10

        db_session.query.return_value.filter.return_value.first.return_value = case
        db_session.query.return_value.filter.return_value.count.return_value = 1
        db_session.query.return_value.order_by.return_value.all.return_value = [
            (5,),   # judge 5
            (5,),   # judge 5
            (7,),   # judge 7 - change 1
            (9,),   # judge 9 - change 2
            (9,),   # judge 9
            (5,),   # judge 5 - change 3
        ]

        result = extractor.extract_bench_hunting(2)

        assert result.case_id == 2
        assert result.bench_changes == 3
        assert result.hunting_index > 0.0
        assert result.level in [
            BenchHuntingLevel.MINIMAL,
            BenchHuntingLevel.MODERATE,
            BenchHuntingLevel.SIGNIFICANT,
        ]


class TestBatchFeatureExtraction:
    """Tests for batch feature extraction."""

    def test_batch_extraction_success(self, extractor, db_session):
        """Test successful batch extraction of multiple cases."""
        extractor.extract_all_features = MagicMock()

        mock_features = MagicMock()
        extractor.extract_all_features.return_value = mock_features

        result = extractor.extract_batch_features([1, 2, 3])

        assert result.total_cases == 3
        assert result.successful == 3
        assert result.failed == 0
        assert len(result.features) == 3

    def test_batch_extraction_with_failures(self, extractor, db_session):
        """Test batch extraction with some failures."""

        def side_effect(case_id):
            if case_id == 2:
                raise ValueError("Database error")
            return MagicMock()

        extractor.extract_all_features = MagicMock(side_effect=side_effect)

        result = extractor.extract_batch_features([1, 2, 3])

        assert result.total_cases == 3
        assert result.successful == 2
        assert result.failed == 1
        assert len(result.error_cases) == 1
        assert result.error_cases[0]["case_id"] == 2


class TestCategorization:
    """Tests for categorization functions."""

    def test_party_delay_categorization(self, extractor):
        """Test party delay level categorization."""
        assert extractor._categorize_party_delay(20.0) == DelayScoreLevel.LOW
        assert extractor._categorize_party_delay(50.0) == DelayScoreLevel.MODERATE
        assert extractor._categorize_party_delay(75.0) == DelayScoreLevel.HIGH
        assert extractor._categorize_party_delay(90.0) == DelayScoreLevel.EXTREME

    def test_bench_hunting_categorization(self, extractor):
        """Test bench hunting level categorization."""
        assert extractor._categorize_bench_hunting(0.5) == BenchHuntingLevel.NO_HUNTING
        assert extractor._categorize_bench_hunting(2.0) == BenchHuntingLevel.MINIMAL
        assert extractor._categorize_bench_hunting(4.0) == BenchHuntingLevel.MODERATE
        assert extractor._categorize_bench_hunting(6.0) == BenchHuntingLevel.SIGNIFICANT
        assert extractor._categorize_bench_hunting(9.0) == BenchHuntingLevel.EXTENSIVE
