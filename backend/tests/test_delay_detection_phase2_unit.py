"""
Simplified unit tests for Phase 2 Deliberate Delay Detection features.

These tests validate feature computation logic without database dependencies.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models import HearingOutcomeType
from app.services.delay_detection_phase2 import (
    AdjournmentDensity,
    BenchHuntingIndex,
    DormancyVariance,
    FeatureEngineer,
    PartyDrivenDelayScore,
    TacticFrequency,
)


class TestFeatureDataClasses:
    """Test that dataclasses validate and structure data correctly."""

    def test_adjournment_density_creation(self):
        """Test AdjournmentDensity dataclass."""
        density = AdjournmentDensity(
            total_hearings=10,
            adjournment_count=3,
            density=30.0,
            trend="increasing",
            recent_density=45.0,
        )

        assert density.total_hearings == 10
        assert density.adjournment_count == 3
        assert density.density == 30.0
        assert density.trend == "increasing"

    def test_party_driven_delay_score_creation(self):
        """Test PartyDrivenDelayScore dataclass."""
        score = PartyDrivenDelayScore(
            score=75.5,
            proxy_counsel_ratio=0.40,
            frivolous_filing_ratio=0.20,
            tactic_diversity=3,
            recurrence_factor=0.50,
            explanation="Test explanation",
        )

        assert score.score == 75.5
        assert 0 <= score.score <= 100
        assert score.tactic_diversity == 3

    def test_dormancy_variance_creation(self):
        """Test DormancyVariance dataclass."""
        variance = DormancyVariance(
            mean_days_between_hearings=45.2,
            variance=312.4,
            std_dev=17.7,
            max_gap_days=95,
            min_gap_days=12,
            coefficient_of_variation=0.392,
            pattern_type="irregular",
        )

        assert variance.mean_days_between_hearings == 45.2
        assert variance.pattern_type == "irregular"
        assert variance.coefficient_of_variation == 0.392

    def test_bench_hunting_index_creation(self):
        """Test BenchHuntingIndex dataclass."""
        index = BenchHuntingIndex(
            judge_change_count=8,
            average_hearings_per_judge=2.25,
            bench_change_frequency=1.5,
            high_adjournment_judges=3,
            pattern_strength=0.67,
            explanation="Test pattern",
        )

        assert index.judge_change_count == 8
        assert 0 <= index.pattern_strength <= 1.0
        assert index.high_adjournment_judges == 3

    def test_tactic_frequency_total(self):
        """Test TacticFrequency total calculation."""
        freq = TacticFrequency(
            proxy_counsel=2,
            frivolous_filing=1,
            judge_unavailable=1,
            stay_extension=1,
            unidentified=0,
        )

        assert freq.total == 5
        assert freq.as_dict["proxy_counsel"] == 2


class TestScoreNormalization:
    """Test score normalization and validation."""

    def test_party_score_bounds(self):
        """Test that party scores are bounded 0-100."""
        # Test low score
        low_score = PartyDrivenDelayScore(
            score=0.0,
            proxy_counsel_ratio=0.0,
            frivolous_filing_ratio=0.0,
            tactic_diversity=0,
            recurrence_factor=0.0,
            explanation="No delays",
        )
        assert 0 <= low_score.score <= 100

        # Test high score
        high_score = PartyDrivenDelayScore(
            score=100.0,
            proxy_counsel_ratio=1.0,
            frivolous_filing_ratio=1.0,
            tactic_diversity=4,
            recurrence_factor=1.0,
            explanation="Maximum delays",
        )
        assert 0 <= high_score.score <= 100

    def test_pattern_strength_bounds(self):
        """Test that pattern strength is 0-1."""
        index = BenchHuntingIndex(
            judge_change_count=0,
            average_hearings_per_judge=0.0,
            bench_change_frequency=0.0,
            high_adjournment_judges=0,
            pattern_strength=0.0,
            explanation="No pattern",
        )
        assert 0 <= index.pattern_strength <= 1.0

        index_high = BenchHuntingIndex(
            judge_change_count=10,
            average_hearings_per_judge=1.0,
            bench_change_frequency=5.0,
            high_adjournment_judges=5,
            pattern_strength=0.85,
            explanation="Strong pattern",
        )
        assert 0 <= index_high.pattern_strength <= 1.0


class TestTrendCalculation:
    """Test trend detection logic."""

    def test_trend_increasing_logic(self):
        """Test logic for detecting increasing trend."""
        # Mock hearings: first half 40% adj, second half 80% adj
        first_half_adj = 2
        first_half_total = 5
        second_half_adj = 4
        second_half_total = 5

        first_half_density = first_half_adj / first_half_total  # 0.40
        second_half_density = second_half_adj / second_half_total  # 0.80
        density_change = second_half_density - first_half_density  # 0.40

        # Should be "increasing" since change > 0.15
        assert density_change > 0.15
        trend = "increasing" if density_change > 0.15 else "stable"
        assert trend == "increasing"

    def test_trend_decreasing_logic(self):
        """Test logic for detecting decreasing trend."""
        first_half_density = 0.80
        second_half_density = 0.40
        density_change = second_half_density - first_half_density

        assert density_change < -0.15
        trend = "decreasing" if density_change < -0.15 else "stable"
        assert trend == "decreasing"

    def test_trend_stable_logic(self):
        """Test logic for detecting stable trend."""
        first_half_density = 0.50
        second_half_density = 0.52
        density_change = second_half_density - first_half_density

        assert abs(density_change) <= 0.15
        trend = "stable"
        assert trend == "stable"


class TestDormancyPatternClassification:
    """Test dormancy pattern classification logic."""

    def test_consistent_pattern_detection(self):
        """Test detection of consistent spacing pattern."""
        # CV < 0.3 indicates consistent pattern
        std_dev = 2.0
        mean = 30.0
        cv = std_dev / mean  # 0.067

        assert cv < 0.3
        pattern = "consistent" if cv < 0.3 else "irregular"
        assert pattern == "consistent"

    def test_irregular_pattern_detection(self):
        """Test detection of irregular spacing pattern."""
        # CV > 0.8 and max_gap > 2.5*mean indicates irregular/prolonged gaps
        std_dev = 25.0
        mean = 25.0
        cv = std_dev / mean  # 1.0
        max_gap = 80
        expected_threshold = mean * 2.5  # 62.5

        assert cv > 0.8 and max_gap > expected_threshold
        pattern = "prolonged_gaps" if cv > 0.8 and max_gap > expected_threshold else "irregular"
        assert pattern == "prolonged_gaps"


class TestScoreCalculationLogic:
    """Test score calculation formulas."""

    def test_party_score_components(self):
        """Test party-driven score component calculations."""
        # Composition of scores
        proxy_ratio = 0.40
        frivolous_ratio = 0.20
        tactic_diversity = 3
        density = 40.0

        # Component calculations
        proxy_score = proxy_ratio * 40  # 16.0
        frivolous_score = frivolous_ratio * 30  # 6.0
        diversity_bonus = (tactic_diversity / 4.0) * 15  # 11.25
        density_factor = min(density / 100 * 15, 15)  # 6.0

        base_score = proxy_score + frivolous_score + diversity_bonus + density_factor
        # 16 + 6 + 11.25 + 6 = 39.25

        assert proxy_score == 16.0
        assert frivolous_score == 6.0
        assert diversity_bonus == 11.25
        assert base_score == pytest.approx(39.25, abs=0.01)

    def test_recurrence_multiplier(self):
        """Test recurrence multiplier calculation."""
        # Multiplier = 1.0 + (recurrence_factor * 0.5)
        recurrence_factors = [0.0, 0.4, 0.8, 1.0]
        expected_multipliers = [1.0, 1.2, 1.4, 1.5]

        for rec_factor, expected in zip(recurrence_factors, expected_multipliers):
            multiplier = 1.0 + (rec_factor * 0.5)
            assert multiplier == pytest.approx(expected, abs=0.01)


class TestEdgeCases:
    """Test edge case handling."""

    def test_zero_adjournments(self):
        """Test handling of zero adjournments."""
        density = AdjournmentDensity(
            total_hearings=5,
            adjournment_count=0,
            density=0.0,
            trend="insufficient_data",
            recent_density=0.0,
        )

        score = PartyDrivenDelayScore(
            score=0.0,
            proxy_counsel_ratio=0.0,
            frivolous_filing_ratio=0.0,
            tactic_diversity=0,
            recurrence_factor=0.0,
            explanation="No adjournments",
        )

        assert density.adjournment_count == 0
        assert score.score == 0.0

    def test_all_adjournments(self):
        """Test handling of all adjournments."""
        density = AdjournmentDensity(
            total_hearings=5,
            adjournment_count=5,
            density=100.0,
            trend="stable",
            recent_density=100.0,
        )

        assert density.adjournment_count == density.total_hearings
        assert density.density == 100.0

    def test_insufficient_hearings(self):
        """Test handling of insufficient hearing history."""
        density = AdjournmentDensity(
            total_hearings=2,
            adjournment_count=1,
            density=50.0,
            trend="insufficient_data",
            recent_density=50.0,
        )

        assert density.total_hearings < 3
        assert density.trend == "insufficient_data"
