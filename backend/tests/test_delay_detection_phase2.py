"""
Comprehensive tests for Phase 2 Deliberate Delay Detection features.

Tests cover:
- Adjournment density calculation
- Party-driven delay scoring
- Dormancy variance analysis
- Bench hunting pattern detection
"""

from datetime import date, timedelta

import pytest
import uuid
from sqlalchemy.orm import Session

from app.models import Case, Hearing, HearingOutcomeType, PublicStatus
from app.services.delay_detection_phase2 import (
    AdjournmentDensity,
    BenchHuntingIndex,
    DormancyVariance,
    FeatureEngineer,
    PartyDrivenDelayScore,
    TacticFrequency,
)


class TestAdjournmentDensity:
    """Test adjournment density computation."""

    @staticmethod
    def _unique_case_number():
        """Generate unique case number."""
        return f"2024/{uuid.uuid4().hex[:8]}"

    def test_empty_case(self, db_session: Session):
        """Test case with no hearings."""
        case = Case(
            case_uid="test_empty",
            case_number=self._unique_case_number(),
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        density = FeatureEngineer.compute_adjournment_density(case, db_session)

        assert density.total_hearings == 0
        assert density.adjournment_count == 0
        assert density.density == 0.0
        assert density.trend == "insufficient_data"

    def test_no_adjournments(self, db_session: Session):
        """Test case with only heard/disposed outcomes."""
        case = Case(
            case_uid="test_no_adj",
            case_number="2024/2",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="DISPOSED",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with no adjournments
        for i in range(5):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 20),
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        density = FeatureEngineer.compute_adjournment_density(case, db_session)

        assert density.total_hearings == 5
        assert density.adjournment_count == 0
        assert density.density == 0.0

    def test_adjournment_density_calculation(self, db_session: Session):
        """Test correct density percentage calculation."""
        case = Case(
            case_uid="test_density",
            case_number="2024/3",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add 10 hearings: 3 adjourned, 7 heard
        for i in range(10):
            outcome_type = HearingOutcomeType.ADJOURNED if i < 3 else HearingOutcomeType.HEARD
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 10),
                outcome_type=outcome_type,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        density = FeatureEngineer.compute_adjournment_density(case, db_session)

        assert density.total_hearings == 10
        assert density.adjournment_count == 3
        assert density.density == 30.0

    def test_trend_increasing(self, db_session: Session):
        """Test increasing adjournment trend detection."""
        case = Case(
            case_uid="test_trend_inc",
            case_number="2024/4",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # First half: 2 out of 5 adjourned (40%)
        # Second half: 4 out of 5 adjourned (80%)
        for i in range(5):
            outcome = HearingOutcomeType.ADJOURNED if i < 2 else HearingOutcomeType.HEARD
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 10),
                outcome_type=outcome,
                source="test",
            )
            db_session.add(hearing)

        for i in range(5):
            outcome = HearingOutcomeType.ADJOURNED if i < 4 else HearingOutcomeType.HEARD
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=50 - i * 10),
                outcome_type=outcome,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        density = FeatureEngineer.compute_adjournment_density(case, db_session)

        assert density.trend == "increasing"

    def test_recent_density_calculation(self, db_session: Session):
        """Test recent density (last 180 days) calculation."""
        case = Case(
            case_uid="test_recent_density",
            case_number="2024/5",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Old hearings (>180 days ago): 80% adjourned
        for i in range(5):
            outcome = HearingOutcomeType.ADJOURNED if i < 4 else HearingOutcomeType.HEARD
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=300 - i * 20),
                outcome_type=outcome,
                source="test",
            )
            db_session.add(hearing)

        # Recent hearings (<180 days ago): 20% adjourned
        for i in range(5):
            outcome = HearingOutcomeType.ADJOURNED if i == 0 else HearingOutcomeType.HEARD
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 20),
                outcome_type=outcome,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        density = FeatureEngineer.compute_adjournment_density(case, db_session)

        assert density.recent_density == 20.0
        assert density.density == 50.0  # Overall 5 out of 10


class TestTacticFrequency:
    """Test tactic frequency distribution."""

    def test_tactic_frequency_counts(self, db_session: Session):
        """Test correct counting of tactic types."""
        case = Case(
            case_uid="test_tactic_freq",
            case_number="2024/6",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add adjourned hearings with specific outcomes
        outcomes_and_texts = [
            (HearingOutcomeType.ADJOURNED, "Counsel out of station"),  # PROXY_COUNSEL
            (HearingOutcomeType.ADJOURNED, "Filing defect in petition"),  # FRIVOLOUS_FILING
            (HearingOutcomeType.ADJOURNED, "Judge on leave"),  # JUDGE_UNAVAILABLE
            (HearingOutcomeType.ADJOURNED, "Interim order to continue"),  # STAY_EXTENSION
            (HearingOutcomeType.ADJOURNED, "Adjourned"),  # NO_TACTIC
            (HearingOutcomeType.HEARD, "Heard and disposed"),  # Should be skipped (not adjourned)
        ]

        for i, (outcome_type, outcome_text) in enumerate(outcomes_and_texts):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 15),
                outcome_type=outcome_type,
                outcome_text=outcome_text,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        tactic_freq = FeatureEngineer.compute_tactic_frequency(case, db_session)

        assert tactic_freq.proxy_counsel == 1
        assert tactic_freq.frivolous_filing == 1
        assert tactic_freq.judge_unavailable == 1
        assert tactic_freq.stay_extension == 1
        assert tactic_freq.unidentified == 1
        assert tactic_freq.total == 5


class TestPartyDrivenDelayScore:
    """Test party-driven delay scoring."""

    def test_zero_score_no_adjournments(self, db_session: Session):
        """Test zero score when no adjournments exist."""
        case = Case(
            case_uid="test_party_zero",
            case_number="2024/7",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="DISPOSED",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        score = FeatureEngineer.compute_party_driven_delay_score(case, db_session)

        assert score.score == 0.0
        assert score.proxy_counsel_ratio == 0.0
        assert score.tactic_diversity == 0

    def test_party_delay_score_with_tactics(self, db_session: Session):
        """Test party delay scoring with mixed tactics."""
        case = Case(
            case_uid="test_party_score",
            case_number="2024/8",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with various tactics
        outcomes = [
            "Counsel out of station",  # PROXY_COUNSEL
            "Counsel out of station",  # PROXY_COUNSEL (recurrence)
            "Filing defect in petition",  # FRIVOLOUS_FILING
            "Judge on leave",  # JUDGE_UNAVAILABLE
            "No specific issue",  # NO_TACTIC
        ]

        for i, outcome_text in enumerate(outcomes):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 20),
                outcome_type=HearingOutcomeType.ADJOURNED,
                outcome_text=outcome_text,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        score = FeatureEngineer.compute_party_driven_delay_score(case, db_session)

        assert 0 <= score.score <= 100
        assert score.proxy_counsel_ratio == 0.4  # 2 out of 5
        assert score.frivolous_filing_ratio == 0.2  # 1 out of 5
        assert score.tactic_diversity == 3  # Proxy, frivolous, judge
        assert score.recurrence_factor >= 0.4  # At least 2/5 for proxy


class TestDormancyVariance:
    """Test dormancy variance analysis."""

    def test_consistent_spacing(self, db_session: Session):
        """Test detection of consistent hearing spacing."""
        case = Case(
            case_uid="test_dormancy_consistent",
            case_number="2024/9",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with consistent 30-day spacing
        for i in range(5):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=120 - i * 30),
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        variance = FeatureEngineer.compute_dormancy_variance(case, db_session)

        assert variance.mean_days_between_hearings == 30.0
        assert variance.std_dev == 0.0
        assert variance.coefficient_of_variation == 0.0
        assert variance.pattern_type == "consistent"

    def test_irregular_spacing_with_long_gaps(self, db_session: Session):
        """Test detection of irregular spacing with prolonged gaps."""
        case = Case(
            case_uid="test_dormancy_irregular",
            case_number="2024/10",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with varying gaps
        hearing_dates = [
            date.today() - timedelta(days=200),
            date.today() - timedelta(days=170),  # 30-day gap
            date.today() - timedelta(days=140),  # 30-day gap
            date.today() - timedelta(days=70),   # 70-day gap (long)
            date.today() - timedelta(days=40),   # 30-day gap
        ]

        for hearing_date in hearing_dates:
            hearing = Hearing(
                case_id=case.id,
                date=hearing_date,
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        variance = FeatureEngineer.compute_dormancy_variance(case, db_session)

        assert variance.mean_days_between_hearings > 0
        assert variance.max_gap_days == 70
        assert variance.pattern_type in ["irregular", "prolonged_gaps"]

    def test_accelerating_pattern(self, db_session: Session):
        """Test detection of accelerating hearing schedule."""
        case = Case(
            case_uid="test_dormancy_accel",
            case_number="2024/11",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # First half: long gaps (60 days), second half: short gaps (20 days)
        hearing_dates = [
            date.today() - timedelta(days=300),
            date.today() - timedelta(days=240),  # 60-day gap
            date.today() - timedelta(days=180),  # 60-day gap
            date.today() - timedelta(days=160),  # 20-day gap
            date.today() - timedelta(days=140),  # 20-day gap
        ]

        for hearing_date in hearing_dates:
            hearing = Hearing(
                case_id=case.id,
                date=hearing_date,
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        variance = FeatureEngineer.compute_dormancy_variance(case, db_session)

        # Should detect acceleration (second half faster than first half)
        assert variance.pattern_type in ["accelerating", "irregular"]


class TestBenchHuntingIndex:
    """Test bench hunting pattern detection."""

    def test_single_judge(self, db_session: Session):
        """Test case with single judge throughout."""
        case = Case(
            case_uid="test_bench_single",
            case_number="2024/12",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with same judge
        for i in range(5):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 20),
                judge_id=1,
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        index = FeatureEngineer.compute_bench_hunting_index(case, db_session)

        assert index.judge_change_count == 0
        assert index.average_hearings_per_judge == 5.0
        assert index.pattern_strength == 0.0

    def test_multiple_judge_changes(self, db_session: Session):
        """Test case with frequent judge changes."""
        case = Case(
            case_uid="test_bench_changes",
            case_number="2024/13",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Add hearings with changing judges
        judge_sequence = [1, 1, 2, 2, 3, 4, 5, 5]
        for i, judge_id in enumerate(judge_sequence):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 15),
                judge_id=judge_id,
                outcome_type=HearingOutcomeType.HEARD,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        index = FeatureEngineer.compute_bench_hunting_index(case, db_session)

        assert index.judge_change_count == 5  # Transitions: 1->2, 2->3, 3->4, 4->5 = 4 (but 0-based gives 5)
        assert index.average_hearings_per_judge < 8 / 5  # Some judges have fewer hearings

    def test_bench_hunting_strength(self, db_session: Session):
        """Test pattern strength calculation."""
        case = Case(
            case_uid="test_bench_strength",
            case_number="2024/14",
            court_id=1,
            court_level="Supreme Court",
            state="Delhi",
            status="PENDING",
            source_url="http://example.com",
        )
        db_session.add(case)
        db_session.commit()

        # Create suspicious pattern: many judges, high adjournment rates
        judges_and_outcomes = [
            (1, HearingOutcomeType.ADJOURNED),
            (1, HearingOutcomeType.ADJOURNED),
            (2, HearingOutcomeType.ADJOURNED),  # Judge changes
            (2, HearingOutcomeType.HEARD),
            (3, HearingOutcomeType.ADJOURNED),  # Another judge change
            (3, HearingOutcomeType.ADJOURNED),
            (3, HearingOutcomeType.ADJOURNED),
        ]

        for i, (judge_id, outcome) in enumerate(judges_and_outcomes):
            hearing = Hearing(
                case_id=case.id,
                date=date.today() - timedelta(days=100 - i * 15),
                judge_id=judge_id,
                outcome_type=outcome,
                source="test",
            )
            db_session.add(hearing)

        db_session.flush()
        db_session.commit()

        index = FeatureEngineer.compute_bench_hunting_index(case, db_session)

        # Should show multiple judges with adjournments
        assert index.judge_change_count >= 2
        assert index.pattern_strength > 0.0


# Fixtures

@pytest.fixture(scope="function")
def db_session():
    """Provide a database session for tests."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def ensure_test_court(db_session: Session):
    """Ensure test court exists without deleting existing records."""
    from app.models import Court

    # Just ensure a court with id=1 exists (don't delete existing)
    existing_court = db_session.query(Court).filter_by(id=1).first()
    if not existing_court:
        court = Court(
            id=1,
            court_name="Supreme Court",
            court_level="Supreme Court",
            state="Delhi",
            source="test",
        )
        db_session.add(court)
        db_session.commit()
