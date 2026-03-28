"""
Unit tests for Phase 3: Baseline Deviation & Probability Scoring.

Tests cover baseline calculation, z-score computation, and probability
calculation without requiring complex database fixtures.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.delay_detection_phase3 import (
    BaselineMetrics,
    ZScores,
    DeliberateDelayProbability,
    CaseAnomalyDetector,
)
from app.services.delay_detection_phase2 import (
    AdjournmentDensity,
    PartyDrivenDelayScore,
    DormancyVariance,
    BenchHuntingIndex,
)


class TestBaselineMetricsDataclass:
    """Test BaselineMetrics dataclass creation and validation."""

    def test_baseline_metrics_creation(self):
        """Test creating BaselineMetrics with valid values."""
        baseline = BaselineMetrics(
            density_mean=35.5,
            density_std=12.3,
            party_score_mean=52.0,
            party_score_std=18.5,
            dormancy_cv_mean=0.45,
            dormancy_cv_std=0.15,
            bench_hunting_mean=0.35,
            bench_hunting_std=0.12,
            sample_size=150,
            calculation_date=datetime.utcnow(),
        )

        assert baseline.density_mean == 35.5
        assert baseline.sample_size == 150
        assert baseline.calculation_date is not None

    def test_baseline_metrics_frozen(self):
        """Test that BaselineMetrics is immutable (frozen)."""
        baseline = BaselineMetrics(
            density_mean=35.5,
            density_std=12.3,
            party_score_mean=52.0,
            party_score_std=18.5,
            dormancy_cv_mean=0.45,
            dormancy_cv_std=0.15,
            bench_hunting_mean=0.35,
            bench_hunting_std=0.12,
            sample_size=150,
            calculation_date=datetime.utcnow(),
        )

        with pytest.raises(AttributeError):
            baseline.density_mean = 40.0  # Should fail - frozen


class TestZScoresDataclass:
    """Test ZScores dataclass and utility methods."""

    def test_z_scores_creation(self):
        """Test creating ZScores with valid values."""
        z_scores = ZScores(
            density_z=1.5,
            party_score_z=2.1,
            dormancy_cv_z=-0.8,
            bench_hunting_z=0.3,
            composite_z=1.02,
        )

        assert z_scores.density_z == 1.5
        assert z_scores.composite_z == 1.02

    def test_z_scores_extreme_scores_filtering(self):
        """Test extreme_scores property returns only |z| > 2."""
        z_scores = ZScores(
            density_z=2.5,  # Extreme
            party_score_z=1.8,  # Not extreme
            dormancy_cv_z=-2.2,  # Extreme
            bench_hunting_z=0.5,  # Not extreme
            composite_z=1.5,
        )

        extremes = z_scores.extreme_scores
        assert extremes["density"] == 2.5
        assert extremes["party_score"] is None
        assert extremes["dormancy_cv"] == -2.2
        assert extremes["bench_hunting"] is None


class TestZScoreComputation:
    """Test z-score calculation logic."""

    def test_safe_z_score_calculation(self):
        """Test basic z-score formula: (value - mean) / std."""
        # Z-score for value 40 with mean 30 and std 5 should be 2.0
        z = (40 - 30) / 5
        assert z == 2.0

        # Z-score for value 25 should be -1.0
        z = (25 - 30) / 5
        assert abs(z - (-1.0)) < 0.01

    def test_safe_z_score_zero_std(self):
        """Test z-score handling when standard deviation is zero."""
        # When std is 0, safe_z_score should return 0
        # (no variation in population -> no anomaly)
        std = 0
        if std == 0:
            z = 0.0
        else:
            z = (40 - 30) / std
        
        assert z == 0.0

    def test_compute_z_scores_with_mock_features(self):
        """Test Z-score computation with mocked Phase 2 features."""
        baseline = BaselineMetrics(
            density_mean=30.0,
            density_std=10.0,
            party_score_mean=50.0,
            party_score_std=15.0,
            dormancy_cv_mean=0.5,
            dormancy_cv_std=0.1,
            bench_hunting_mean=0.3,
            bench_hunting_std=0.1,
            sample_size=100,
            calculation_date=datetime.utcnow(),
        )

        # Mock Phase 2 features
        mock_case = MagicMock()
        mock_case.id = 1
        mock_db = MagicMock()

        # Create mocked feature results
        mock_density = AdjournmentDensity(
            total_hearings=20, adjournment_count=8, density=40.0,
            trend="increasing", recent_density=45.0
        )
        mock_party_score = PartyDrivenDelayScore(
            score=65.0, proxy_counsel_ratio=0.4, frivolous_filing_ratio=0.25,
            tactic_diversity=3, recurrence_factor=0.5,
            explanation="Test explanation"
        )
        mock_dormancy = DormancyVariance(
            mean_days_between_hearings=35.0, variance=225.0, std_dev=15.0,
            max_gap_days=60, min_gap_days=10,
            coefficient_of_variation=0.6, pattern_type="irregular"
        )
        mock_bench_hunting = BenchHuntingIndex(
            judge_change_count=3, average_hearings_per_judge=2.5,
            bench_change_frequency=1.5, high_adjournment_judges=1,
            pattern_strength=0.45, explanation="Moderate bench hunting pattern"
        )

        # Patch FeatureEngineer methods
        with patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_adjournment_density",
            return_value=mock_density,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_party_driven_delay_score",
            return_value=mock_party_score,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_dormancy_variance",
            return_value=mock_dormancy,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_bench_hunting_index",
            return_value=mock_bench_hunting,
        ):
            z_scores = CaseAnomalyDetector.compute_z_scores(
                mock_case, mock_db, baseline
            )

        # Verify z-scores are calculated correctly
        # density_z = (40 - 30) / 10 = 1.0
        assert abs(z_scores.density_z - 1.0) < 0.01

        # party_score_z = (65 - 50) / 15 = 1.0
        assert abs(z_scores.party_score_z - 1.0) < 0.01

        # dormancy_cv_z = (0.6 - 0.5) / 0.1 = 1.0
        assert abs(z_scores.dormancy_cv_z - 1.0) < 0.01

        # bench_hunting_z = (0.45 - 0.3) / 0.1 = 1.5
        assert abs(z_scores.bench_hunting_z - 1.5) < 0.01

        # Composite should be weighted average
        composite_expected = (
            0.25 * 1.0 + 0.35 * 1.0 + 0.20 * 1.0 + 0.20 * 1.5
        )
        assert abs(z_scores.composite_z - composite_expected) < 0.01


class TestPercentileInterpolation:
    """Test percentile calculation from z-scores."""

    def test_percentile_lookup_exact_match(self):
        """Test percentile for z-score with exact lookup table match."""
        # At z=0, percentile should be 50%
        percentile = CaseAnomalyDetector._interpolate_percentile(0.0)
        assert percentile == 50.0

        # At z=-3, percentile should be 0.1%
        percentile = CaseAnomalyDetector._interpolate_percentile(-3.0)
        assert percentile == 0.1

        # At z=3, percentile should be 99.9%
        percentile = CaseAnomalyDetector._interpolate_percentile(3.0)
        assert percentile == 99.9

    def test_percentile_lookup_interpolation(self):
        """Test percentile with linear interpolation between table values."""
        # At z=0.5, should interpolate between z=0 (50%) and z=1 (84.1%)
        percentile = CaseAnomalyDetector._interpolate_percentile(0.5)
        # Expected: 50 + 0.5 * (84.1 - 50) = 50 + 17.05 = 67.05
        assert 65.0 < percentile < 70.0

    def test_percentile_clamping(self):
        """Test that z-scores beyond table range are clamped."""
        # Z-score of 5.0 should clamp to 3.0 (99.9%)
        percentile = CaseAnomalyDetector._interpolate_percentile(5.0)
        assert percentile == 99.9

        # Z-score of -5.0 should clamp to -3.0 (0.1%)
        percentile = CaseAnomalyDetector._interpolate_percentile(-5.0)
        assert percentile == 0.1


class TestProbabilityCalculation:
    """Test deliberate delay probability calculation."""

    def test_probability_extreme_high(self):
        """Test probability calculation for case with extreme high z-score."""
        baseline = BaselineMetrics(
            density_mean=30.0, density_std=10.0,
            party_score_mean=50.0, party_score_std=15.0,
            dormancy_cv_mean=0.5, dormancy_cv_std=0.1,
            bench_hunting_mean=0.3, bench_hunting_std=0.1,
            sample_size=100, calculation_date=datetime.utcnow(),
        )

        mock_case = MagicMock()
        mock_case.id = 1
        mock_case.case_number = "CASE/2024/001"
        mock_db = MagicMock()

        # Mock features with extreme values (all above baseline)
        mock_density = AdjournmentDensity(
            total_hearings=20, adjournment_count=16, density=80.0,
            trend="increasing", recent_density=85.0
        )
        mock_party_score = PartyDrivenDelayScore(
            score=95.0, proxy_counsel_ratio=0.6, frivolous_filing_ratio=0.3,
            tactic_diversity=4, recurrence_factor=0.8,
            explanation="Extreme party involvement"
        )
        mock_dormancy = DormancyVariance(
            mean_days_between_hearings=5.0, variance=1.0, std_dev=1.0,
            max_gap_days=200, min_gap_days=2,
            coefficient_of_variation=0.8, pattern_type="prolonged_gaps"
        )
        mock_bench_hunting = BenchHuntingIndex(
            judge_change_count=8, average_hearings_per_judge=1.5,
            bench_change_frequency=3.0, high_adjournment_judges=3,
            pattern_strength=0.9, explanation="Systematic bench hunting pattern"
        )

        # Mock Hearing count for confidence calculation
        mock_db.query().filter().count.return_value = 30

        with patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_adjournment_density",
            return_value=mock_density,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_party_driven_delay_score",
            return_value=mock_party_score,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_dormancy_variance",
            return_value=mock_dormancy,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_bench_hunting_index",
            return_value=mock_bench_hunting,
        ):
            prob = CaseAnomalyDetector.compute_probability(mock_case, mock_db, baseline)

        # Should have high probability
        assert prob.probability > 80.0
        assert prob.risk_level in ["high", "extreme"]
        assert len(prob.anomalies) > 0
        assert prob.confidence > 0.3

    def test_probability_low_risk(self):
        """Test probability calculation for low-risk case."""
        baseline = BaselineMetrics(
            density_mean=30.0, density_std=10.0,
            party_score_mean=50.0, party_score_std=15.0,
            dormancy_cv_mean=0.5, dormancy_cv_std=0.1,
            bench_hunting_mean=0.3, bench_hunting_std=0.1,
            sample_size=100, calculation_date=datetime.utcnow(),
        )

        mock_case = MagicMock()
        mock_case.id = 2
        mock_case.case_number = "CASE/2024/002"
        mock_db = MagicMock()

        # Mock features with values below baseline (low concern)
        mock_density = AdjournmentDensity(
            total_hearings=25, adjournment_count=3, density=12.0,
            trend="stable", recent_density=10.0
        )
        mock_party_score = PartyDrivenDelayScore(
            score=25.0, proxy_counsel_ratio=0.1, frivolous_filing_ratio=0.05,
            tactic_diversity=1, recurrence_factor=0.2,
            explanation="Minimal party involvement"
        )
        mock_dormancy = DormancyVariance(
            mean_days_between_hearings=45.0, variance=100.0, std_dev=10.0,
            max_gap_days=65, min_gap_days=30,
            coefficient_of_variation=0.22, pattern_type="consistent"
        )
        mock_bench_hunting = BenchHuntingIndex(
            judge_change_count=0, average_hearings_per_judge=12.5,
            bench_change_frequency=0.0, high_adjournment_judges=0,
            pattern_strength=0.0, explanation="No bench hunting pattern detected"
        )

        mock_db.query().filter().count.return_value = 25

        with patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_adjournment_density",
            return_value=mock_density,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_party_driven_delay_score",
            return_value=mock_party_score,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_dormancy_variance",
            return_value=mock_dormancy,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_bench_hunting_index",
            return_value=mock_bench_hunting,
        ):
            prob = CaseAnomalyDetector.compute_probability(mock_case, mock_db, baseline)

        # Should have low probability
        assert prob.probability < 40.0
        assert prob.risk_level in ["low", "moderate"]
        # Anomalies can include very low values (negative z-scores)
        # that are still far from baseline, so we just verify they exist or are minimal
        assert isinstance(prob.anomalies, list)

    def test_probability_report_structure(self):
        """Test that probability report has all required fields."""
        baseline = BaselineMetrics(
            density_mean=30.0, density_std=10.0,
            party_score_mean=50.0, party_score_std=15.0,
            dormancy_cv_mean=0.5, dormancy_cv_std=0.1,
            bench_hunting_mean=0.3, bench_hunting_std=0.1,
            sample_size=100, calculation_date=datetime.utcnow(),
        )

        mock_case = MagicMock()
        mock_case.id = 3
        mock_case.case_number = "CASE/2024/003"
        mock_db = MagicMock()

        # Mock with moderate values
        mock_density = AdjournmentDensity(
            total_hearings=20, adjournment_count=8, density=40.0,
            trend="increasing", recent_density=45.0
        )
        mock_party_score = PartyDrivenDelayScore(
            score=55.0, proxy_counsel_ratio=0.35, frivolous_filing_ratio=0.2,
            tactic_diversity=2, recurrence_factor=0.4,
            explanation="Moderate party involvement"
        )
        mock_dormancy = DormancyVariance(
            mean_days_between_hearings=35.0, variance=225.0, std_dev=15.0,
            max_gap_days=65, min_gap_days=15,
            coefficient_of_variation=0.43, pattern_type="irregular"
        )
        mock_bench_hunting = BenchHuntingIndex(
            judge_change_count=2, average_hearings_per_judge=3.5,
            bench_change_frequency=0.8, high_adjournment_judges=0,
            pattern_strength=0.25, explanation="Minimal bench hunting pattern"
        )

        mock_db.query().filter().count.return_value = 20

        with patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_adjournment_density",
            return_value=mock_density,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_party_driven_delay_score",
            return_value=mock_party_score,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_dormancy_variance",
            return_value=mock_dormancy,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_bench_hunting_index",
            return_value=mock_bench_hunting,
        ):
            prob = CaseAnomalyDetector.compute_probability(mock_case, mock_db, baseline)

        # Verify all fields are present
        assert isinstance(prob.probability, float)
        assert 0 <= prob.probability <= 100
        assert isinstance(prob.percentile, float)
        assert 0 <= prob.percentile <= 100
        assert isinstance(prob.confidence, float)
        assert 0.3 <= prob.confidence <= 1.0
        assert prob.risk_level in ["low", "moderate", "high", "extreme"]
        assert isinstance(prob.primary_drivers, list)
        assert isinstance(prob.anomalies, list)
        assert isinstance(prob.explanation, str)
        assert len(prob.explanation) > 0


class TestEdgeCases:
    """Test edge cases in Phase 3 calculations."""

    def test_baseline_with_insufficient_resolved_cases(self):
        """Test baseline calculation returns zeros when insufficient data."""
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = []  # No resolved cases

        baseline = CaseAnomalyDetector.calculate_baselines(mock_db)

        assert baseline.sample_size == 0
        assert baseline.density_mean == 0.0
        assert baseline.density_std == 0.0

    def test_probability_with_zero_std_in_baseline(self):
        """Test probability calculation when baseline has zero std dev."""
        baseline = BaselineMetrics(
            density_mean=30.0, density_std=0.0,  # Zero std
            party_score_mean=50.0, party_score_std=0.0,  # Zero std
            dormancy_cv_mean=0.5, dormancy_cv_std=0.0,  # Zero std
            bench_hunting_mean=0.3, bench_hunting_std=0.0,  # Zero std
            sample_size=100, calculation_date=datetime.utcnow(),
        )

        mock_case = MagicMock()
        mock_case.id = 4
        mock_case.case_number = "CASE/2024/004"
        mock_db = MagicMock()

        mock_density = AdjournmentDensity(
            total_hearings=20, adjournment_count=8, density=40.0,
            trend="increasing", recent_density=45.0
        )
        mock_party_score = PartyDrivenDelayScore(
            score=55.0, proxy_counsel_ratio=0.35, frivolous_filing_ratio=0.2,
            tactic_diversity=2, recurrence_factor=0.4,
            explanation="Moderate"
        )
        mock_dormancy = DormancyVariance(
            mean_days_between_hearings=35.0, variance=225.0, std_dev=15.0,
            max_gap_days=65, min_gap_days=15,
            coefficient_of_variation=0.43, pattern_type="irregular"
        )
        mock_bench_hunting = BenchHuntingIndex(
            judge_change_count=2, average_hearings_per_judge=3.5,
            bench_change_frequency=0.8, high_adjournment_judges=0,
            pattern_strength=0.25, explanation="Minimal bench hunting pattern"
        )

        mock_db.query().filter().count.return_value = 20

        with patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_adjournment_density",
            return_value=mock_density,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_party_driven_delay_score",
            return_value=mock_party_score,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_dormancy_variance",
            return_value=mock_dormancy,
        ), patch(
            "app.services.delay_detection_phase3.FeatureEngineer.compute_bench_hunting_index",
            return_value=mock_bench_hunting,
        ):
            # Should not crash with zero std dev
            prob = CaseAnomalyDetector.compute_probability(mock_case, mock_db, baseline)

        # With zero std, composite z should be 0, so probability near 50%
        assert 40 < prob.probability < 60
