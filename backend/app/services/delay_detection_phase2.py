"""
Feature engineering and pattern analysis for deliberate delay detection.

This module implements Phase 2 of the Deliberate Delay Detection system,
focusing on extracting quantitative features from case histories that indicate
deliberate delay tactics: adjournment density, party-driven delay scores,
dormancy variance, and bench hunting patterns.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Case, Hearing, HearingOutcomeType
from app.services.adjournment import (
    AdjournmentTacticClassifier,
    DelayTactic,
    TacticClassification,
)


@dataclass(frozen=True)
class AdjournmentDensity:
    """Adjournment density metrics for a case.

    Attributes:
        total_hearings: Total substantive + adjourned hearings.
        adjournment_count: Number of adjourned hearings.
        density: Percentage of hearings that were adjourned (0-100).
        trend: Moving trend indicator ('increasing', 'decreasing', 'stable', 'insufficient_data').
        recent_density: Adjournment density in last 6 months.
    """

    total_hearings: int
    adjournment_count: int
    density: float
    trend: str
    recent_density: float


@dataclass(frozen=True)
class TacticFrequency:
    """Frequency distribution of identified delay tactics.

    Attributes:
        proxy_counsel: Count of proxies/counsel unavailability adjournments.
        frivolous_filing: Count of procedural defect adjournments.
        judge_unavailable: Count of judge unavailability adjournments.
        stay_extension: Count of interim order continuation adjournments.
        unidentified: Count of adjournments without identified tactic.
    """

    proxy_counsel: int
    frivolous_filing: int
    judge_unavailable: int
    stay_extension: int
    unidentified: int

    @property
    def total(self) -> int:
        """Total adjournments across all tactics."""
        return (
            self.proxy_counsel
            + self.frivolous_filing
            + self.judge_unavailable
            + self.stay_extension
            + self.unidentified
        )

    @property
    def as_dict(self) -> dict[str, int]:
        """Return tactic frequencies as dictionary."""
        return {
            "proxy_counsel": self.proxy_counsel,
            "frivolous_filing": self.frivolous_filing,
            "judge_unavailable": self.judge_unavailable,
            "stay_extension": self.stay_extension,
            "unidentified": self.unidentified,
        }


@dataclass(frozen=True)
class PartyDrivenDelayScore:
    """Party-driven delay score based on pattern of legal maneuvers.

    Attributes:
        score: Composite score 0-100 indicating degree of party involvement in delays.
        proxy_counsel_ratio: Ratio of proxy counsel adjournments to total adjournments.
        frivolous_filing_ratio: Ratio of procedural defect adjournments to total adjournments.
        tactic_diversity: Number of distinct tactics used (0-4).
        recurrence_factor: Multiplier for repeated use of same tactic.
        explanation: Human-readable explanation of score composition.
    """

    score: float
    proxy_counsel_ratio: float
    frivolous_filing_ratio: float
    tactic_diversity: int
    recurrence_factor: float
    explanation: str


@dataclass(frozen=True)
class DormancyVariance:
    """Variance analysis of dormancy periods between hearings.

    Attributes:
        mean_days_between_hearings: Average days between consecutive hearings.
        variance: Variance of gap lengths (in days²).
        std_dev: Standard deviation of gap lengths (in days).
        max_gap_days: Longest gap between any two consecutive hearings.
        min_gap_days: Shortest gap between any two consecutive hearings.
        coefficient_of_variation: Normalized measure of gap variability (std_dev / mean).
        pattern_type: Classification of dormancy pattern ('consistent', 'irregular', 'prolonged_gaps', 'accelerating').
    """

    mean_days_between_hearings: float
    variance: float
    std_dev: float
    max_gap_days: int
    min_gap_days: int
    coefficient_of_variation: float
    pattern_type: str


@dataclass(frozen=True)
class BenchHuntingIndex:
    """Bench hunting pattern detection and scoring.

    Judge bench hunting occurs when parties repeatedly request adjournments
    or file new applications to change assigned judges/benches.

    Attributes:
        judge_change_count: Number of judge changes in case history.
        average_hearings_per_judge: Average number of hearings per judge assignment.
        bench_change_frequency: Changes per year (0-12).
        high_adjournment_judges: Count of judges with >50% adjournment rate.
        pattern_strength: Confidence score 0-1 indicating bench hunting likelihood.
        explanation: Human-readable pattern description.
    """

    judge_change_count: int
    average_hearings_per_judge: float
    bench_change_frequency: float
    high_adjournment_judges: int
    pattern_strength: float
    explanation: str


class FeatureEngineer:
    """Extract and compute Phase 2 features from case hearing histories."""

    # Configuration constants
    RECENT_PERIOD_DAYS = 180  # 6 months for "recent" analysis
    MIN_HEARINGS_FOR_PATTERN = 3
    MIN_DAYS_BETWEEN_HEARINGS = 1  # Minimum realistic gap

    @classmethod
    def compute_adjournment_density(cls, case: Case, db: Session) -> AdjournmentDensity:
        """Compute adjournment density and trend for a case.

        Args:
            case: The case to analyze.
            db: Database session for querying hearings.

        Returns:
            AdjournmentDensity containing metrics and trend analysis.
        """
        # Query all hearings for the case, ordered by date
        hearings = (
            db.execute(select(Hearing).where(Hearing.case_id == case.id).order_by(Hearing.date))
            .scalars()
            .all()
        )

        if not hearings:
            return AdjournmentDensity(
                total_hearings=0,
                adjournment_count=0,
                density=0.0,
                trend="insufficient_data",
                recent_density=0.0,
            )

        # Count adjourned hearings
        adjourned_hearings = [h for h in hearings if h.outcome_type == HearingOutcomeType.ADJOURNED]
        total_hearings = len(hearings)
        adjournment_count = len(adjourned_hearings)

        # Calculate overall density
        density = (adjournment_count / total_hearings * 100) if total_hearings > 0 else 0.0

        # Calculate recent density (last 6 months)
        today = date.today()
        recent_cutoff = today - timedelta(days=cls.RECENT_PERIOD_DAYS)
        recent_hearings = [h for h in hearings if h.date >= recent_cutoff]
        recent_adjourned = [h for h in recent_hearings if h.outcome_type == HearingOutcomeType.ADJOURNED]
        recent_density = (
            (len(recent_adjourned) / len(recent_hearings) * 100)
            if recent_hearings
            else 0.0
        )

        # Calculate trend
        trend = cls._calculate_adjournment_trend(adjourned_hearings, hearings)

        return AdjournmentDensity(
            total_hearings=total_hearings,
            adjournment_count=adjournment_count,
            density=round(density, 2),
            trend=trend,
            recent_density=round(recent_density, 2),
        )

    @classmethod
    def _calculate_adjournment_trend(
        cls,
        adjourned_hearings: list[Hearing],
        all_hearings: list[Hearing],
    ) -> str:
        """Calculate trend of adjournment frequency over time.

        Args:
            adjourned_hearings: List of adjourned hearings in chronological order.
            all_hearings: List of all hearings in chronological order.

        Returns:
            Trend classification ('increasing', 'decreasing', 'stable', 'insufficient_data').
        """
        if len(all_hearings) < cls.MIN_HEARINGS_FOR_PATTERN:
            return "insufficient_data"

        # Divide hearings into two equal time periods
        midpoint = len(all_hearings) // 2
        first_half = all_hearings[:midpoint]
        second_half = all_hearings[midpoint:]

        # Count adjournments in each half
        first_half_adj = sum(1 for h in first_half if h.outcome_type == HearingOutcomeType.ADJOURNED)
        second_half_adj = sum(1 for h in second_half if h.outcome_type == HearingOutcomeType.ADJOURNED)

        first_half_density = (first_half_adj / len(first_half)) if first_half else 0
        second_half_density = (second_half_adj / len(second_half)) if second_half else 0

        # Determine trend based on density change
        density_change = second_half_density - first_half_density

        if density_change > 0.15:  # >15% increase
            return "increasing"
        elif density_change < -0.15:  # >15% decrease
            return "decreasing"
        else:
            return "stable"

    @classmethod
    def compute_tactic_frequency(cls, case: Case, db: Session) -> TacticFrequency:
        """Analyze frequency of each delay tactic in case adjournments.

        Args:
            case: The case to analyze.
            db: Database session for querying hearings.

        Returns:
            TacticFrequency with distribution across tactics.
        """
        # Query adjourned hearings for this case
        adjourned_hearings = (
            db.execute(
                select(Hearing).where(
                    (Hearing.case_id == case.id)
                    & (Hearing.outcome_type == HearingOutcomeType.ADJOURNED)
                )
            )
            .scalars()
            .all()
        )

        # Classify each adjournment using Phase 1 classifier
        tactic_counts = {tactic: 0 for tactic in DelayTactic}

        for hearing in adjourned_hearings:
            if hearing.outcome_text:
                classification = AdjournmentTacticClassifier.classify_tactic(hearing.outcome_text)
                tactic_counts[classification.tactic] += 1

        return TacticFrequency(
            proxy_counsel=tactic_counts.get(DelayTactic.PROXY_COUNSEL, 0),
            frivolous_filing=tactic_counts.get(DelayTactic.FRIVOLOUS_FILING, 0),
            judge_unavailable=tactic_counts.get(DelayTactic.JUDGE_UNAVAILABLE, 0),
            stay_extension=tactic_counts.get(DelayTactic.STAY_EXTENSION, 0),
            unidentified=tactic_counts.get(DelayTactic.NO_TACTIC_IDENTIFIED, 0),
        )

    @classmethod
    def compute_party_driven_delay_score(
        cls,
        case: Case,
        db: Session,
        density: Optional[AdjournmentDensity] = None,
        tactic_freq: Optional[TacticFrequency] = None,
    ) -> PartyDrivenDelayScore:
        """Compute party-driven delay score based on tactical adjournments.

        This score estimates the degree to which parties (vs. systemic factors)
        are driving delays through deliberate maneuvers.

        Args:
            case: The case to analyze.
            db: Database session.
            density: Pre-computed AdjournmentDensity (computed if not provided).
            tactic_freq: Pre-computed TacticFrequency (computed if not provided).

        Returns:
            PartyDrivenDelayScore with composite scoring.
        """
        if density is None:
            density = cls.compute_adjournment_density(case, db)

        if tactic_freq is None:
            tactic_freq = cls.compute_tactic_frequency(case, db)

        if density.adjournment_count == 0:
            return PartyDrivenDelayScore(
                score=0.0,
                proxy_counsel_ratio=0.0,
                frivolous_filing_ratio=0.0,
                tactic_diversity=0,
                recurrence_factor=1.0,
                explanation="No adjournments detected; no party-driven delays indicated.",
            )

        # Calculate ratios
        proxy_ratio = tactic_freq.proxy_counsel / density.adjournment_count
        frivolous_ratio = tactic_freq.frivolous_filing / density.adjournment_count

        # Count number of distinct tactics used
        tactic_diversity = sum(
            1
            for count in [
                tactic_freq.proxy_counsel,
                tactic_freq.frivolous_filing,
                tactic_freq.judge_unavailable,
                tactic_freq.stay_extension,
            ]
            if count > 0
        )

        # Calculate recurrence factor (reward repeated use of same tactic)
        # If one tactic dominates, it's more likely deliberate
        max_tactic_count = max(
            tactic_freq.proxy_counsel,
            tactic_freq.frivolous_filing,
            tactic_freq.judge_unavailable,
            tactic_freq.stay_extension,
        )
        recurrence_factor = (max_tactic_count / density.adjournment_count) if density.adjournment_count > 0 else 0

        # Composite score calculation (0-100)
        # Base score from proxy counsel (direct party action): 0-40 points
        proxy_score = proxy_ratio * 40

        # Bonus for frivolous filing (deliberate procedural manipulation): 0-30 points
        frivolous_score = frivolous_ratio * 30

        # Diversity bonus: using multiple tactics suggests coordinated effort: 0-15 points
        diversity_bonus = (tactic_diversity / 4.0) * 15

        # Recurrence multiplier: repeated tactics are more suspicious: 1.0-1.5x
        recurrence_multiplier = 1.0 + (recurrence_factor * 0.5)

        # Density factor: higher adjournment density increases suspicion: 0-15 points
        density_factor = min(density.density / 100 * 15, 15)

        base_score = proxy_score + frivolous_score + diversity_bonus + density_factor
        final_score = base_score * recurrence_multiplier
        final_score = min(100.0, max(0.0, final_score))  # Clamp to 0-100

        explanation = (
            f"Party-driven delay score: {final_score:.1f}/100. "
            f"Proxy counsel tactics: {proxy_ratio:.1%}, "
            f"Frivolous filing: {frivolous_ratio:.1%}, "
            f"Tactic diversity: {tactic_diversity}/4, "
            f"Density: {density.density:.1f}%."
        )

        return PartyDrivenDelayScore(
            score=round(final_score, 1),
            proxy_counsel_ratio=round(proxy_ratio, 3),
            frivolous_filing_ratio=round(frivolous_ratio, 3),
            tactic_diversity=tactic_diversity,
            recurrence_factor=round(recurrence_factor, 3),
            explanation=explanation,
        )

    @classmethod
    def compute_dormancy_variance(cls, case: Case, db: Session) -> DormancyVariance:
        """Analyze variance in gaps between consecutive hearings.

        Regular adjournments with consistent spacing suggest systemic delays.
        High variance with occasional long gaps suggests tactical manipulation.

        Args:
            case: The case to analyze.
            db: Database session.

        Returns:
            DormancyVariance with statistical analysis of hearing gaps.
        """
        # Query all hearings in chronological order
        hearings = (
            db.execute(select(Hearing).where(Hearing.case_id == case.id).order_by(Hearing.date))
            .scalars()
            .all()
        )

        if len(hearings) < cls.MIN_HEARINGS_FOR_PATTERN:
            return DormancyVariance(
                mean_days_between_hearings=0.0,
                variance=0.0,
                std_dev=0.0,
                max_gap_days=0,
                min_gap_days=0,
                coefficient_of_variation=0.0,
                pattern_type="insufficient_data",
            )

        # Calculate gaps between consecutive hearings
        gaps = []
        for i in range(1, len(hearings)):
            gap_days = (hearings[i].date - hearings[i - 1].date).days
            if gap_days >= cls.MIN_DAYS_BETWEEN_HEARINGS:
                gaps.append(gap_days)

        if not gaps or len(gaps) < cls.MIN_HEARINGS_FOR_PATTERN - 1:
            return DormancyVariance(
                mean_days_between_hearings=0.0,
                variance=0.0,
                std_dev=0.0,
                max_gap_days=0,
                min_gap_days=0,
                coefficient_of_variation=0.0,
                pattern_type="insufficient_data",
            )

        # Calculate statistics
        mean_gap = statistics.mean(gaps)
        max_gap = max(gaps)
        min_gap = min(gaps)

        try:
            variance = statistics.variance(gaps) if len(gaps) > 1 else 0.0
            std_dev = statistics.stdev(gaps) if len(gaps) > 1 else 0.0
        except ValueError:
            variance = 0.0
            std_dev = 0.0

        # Coefficient of variation (normalized by mean)
        cv = (std_dev / mean_gap) if mean_gap > 0 else 0.0

        # Classify pattern type
        pattern_type = cls._classify_dormancy_pattern(mean_gap, cv, max_gap, hearings)

        return DormancyVariance(
            mean_days_between_hearings=round(mean_gap, 1),
            variance=round(variance, 1),
            std_dev=round(std_dev, 1),
            max_gap_days=max_gap,
            min_gap_days=min_gap,
            coefficient_of_variation=round(cv, 3),
            pattern_type=pattern_type,
        )

    @classmethod
    def _classify_dormancy_pattern(
        cls,
        mean_gap: float,
        cv: float,
        max_gap: int,
        hearings: list[Hearing],
    ) -> str:
        """Classify dormancy pattern based on gap statistics.

        Args:
            mean_gap: Mean days between hearings.
            cv: Coefficient of variation.
            max_gap: Maximum gap between any two hearings.
            hearings: List of all hearings.

        Returns:
            Pattern classification string.
        """
        # High consistency (CV < 0.3) suggests systemic delays
        if cv < 0.3:
            return "consistent"

        # High variability with occasional very long gaps
        if cv > 0.8 and max_gap > mean_gap * 2.5:
            # Check if long gaps correlate with adjournments
            case_id = hearings[0].case_id if hearings else None
            if case_id:
                return "prolonged_gaps"
            return "irregular"

        # Accelerating pattern: gaps decrease over time
        first_half_gaps = []
        second_half_gaps = []
        for i in range(1, len(hearings)):
            gap_days = (hearings[i].date - hearings[i - 1].date).days
            if gap_days >= cls.MIN_DAYS_BETWEEN_HEARINGS:
                if i <= len(hearings) // 2:
                    first_half_gaps.append(gap_days)
                else:
                    second_half_gaps.append(gap_days)

        if first_half_gaps and second_half_gaps:
            first_mean = statistics.mean(first_half_gaps)
            second_mean = statistics.mean(second_half_gaps)
            if second_mean < first_mean * 0.7:  # >30% reduction
                return "accelerating"

        return "irregular"

    @classmethod
    def compute_bench_hunting_index(case: Case, db: Session) -> BenchHuntingIndex:
        """Detect bench hunting patterns (judge/bench changes).

        Bench hunting occurs when parties repeatedly cause judge changes
        through adjournments or procedural maneuvers.

        Args:
            case: The case to analyze.
            db: Database session.

        Returns:
            BenchHuntingIndex with pattern analysis.
        """
        # Query all hearings with judge assignments
        hearings = (
            db.execute(select(Hearing).where(Hearing.case_id == case.id).order_by(Hearing.date))
            .scalars()
            .all()
        )

        if len(hearings) < 2:
            return BenchHuntingIndex(
                judge_change_count=0,
                average_hearings_per_judge=0.0,
                bench_change_frequency=0.0,
                high_adjournment_judges=0,
                pattern_strength=0.0,
                explanation="Insufficient hearing history for bench hunting analysis.",
            )

        # Track judge changes
        judge_sequence = []
        for hearing in hearings:
            if hearing.judge_id:
                judge_sequence.append(hearing.judge_id)

        if not judge_sequence:
            return BenchHuntingIndex(
                judge_change_count=0,
                average_hearings_per_judge=0.0,
                bench_change_frequency=0.0,
                high_adjournment_judges=0,
                pattern_strength=0.0,
                explanation="No judge assignment data available.",
            )

        # Count judge changes (transitions between different judges)
        judge_changes = 0
        for i in range(1, len(judge_sequence)):
            if judge_sequence[i] != judge_sequence[i - 1]:
                judge_changes += 1

        unique_judges = len(set(judge_sequence))
        avg_hearings_per_judge = len(judge_sequence) / unique_judges if unique_judges > 0 else 0

        # Calculate change frequency (per year)
        case_duration_days = (hearings[-1].date - hearings[0].date).days
        case_duration_years = case_duration_days / 365.25 if case_duration_days > 0 else 1
        change_frequency = judge_changes / case_duration_years

        # Identify judges with high adjournment rates
        high_adj_judges = 0
        judge_adjournments: dict[int, tuple[int, int]] = {}  # judge_id -> (adj_count, total_count)

        for hearing in hearings:
            if hearing.judge_id:
                if hearing.judge_id not in judge_adjournments:
                    judge_adjournments[hearing.judge_id] = (0, 0)

                adj_count, total_count = judge_adjournments[hearing.judge_id]
                total_count += 1

                if hearing.outcome_type == HearingOutcomeType.ADJOURNED:
                    adj_count += 1

                judge_adjournments[hearing.judge_id] = (adj_count, total_count)

        # Count judges with >50% adjournment rate
        for adj_count, total_count in judge_adjournments.values():
            if total_count >= 3 and (adj_count / total_count) > 0.5:  # At least 3 hearings
                high_adj_judges += 1

        # Calculate pattern strength (0-1)
        # Factors: frequency of changes, ratio of unique judges, high-adj judges
        frequency_factor = min(change_frequency / 2, 1.0)  # Normalize to 0-1
        uniqueness_factor = min(unique_judges / len(hearings), 0.5)  # Cap at 0.5
        high_adj_factor = (high_adj_judges / unique_judges) if unique_judges > 0 else 0

        pattern_strength = (frequency_factor * 0.4) + (uniqueness_factor * 0.35) + (high_adj_factor * 0.25)
        pattern_strength = min(1.0, max(0.0, pattern_strength))

        explanation = (
            f"Bench hunting analysis: {judge_changes} judge changes across "
            f"{unique_judges} judges in {len(hearings)} hearings. "
            f"Change frequency: {change_frequency:.2f}/year, "
            f"{high_adj_judges} judges with >50% adjournment rate. "
            f"Pattern strength: {pattern_strength:.2%}."
        )

        return BenchHuntingIndex(
            judge_change_count=judge_changes,
            average_hearings_per_judge=round(avg_hearings_per_judge, 2),
            bench_change_frequency=round(change_frequency, 2),
            high_adjournment_judges=high_adj_judges,
            pattern_strength=round(pattern_strength, 3),
            explanation=explanation,
        )
