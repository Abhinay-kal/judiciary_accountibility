"""
Baseline Deviation Analysis and Deliberate Delay Probability Calculation.

This module implements Phase 3 of the Deliberate Delay Detection system,
focusing on calculating how anomalous a case is compared to baseline metrics
and computing a final deliberate_delay_probability score (0-100).

Phase 3 takes outputs from Phase 2 (features) and compares them against:
1. Population baselines (calculated from resolved cases)
2. Court/judge-specific baselines (optional)
3. Case type baselines (optional)

The system uses Z-score standardization to detect outliers and combines
multiple z-scores into a final probability using Gaussian CDF approximation.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Case, Hearing, HearingOutcomeType
from app.services.delay_detection_phase2 import (
    AdjournmentDensity,
    BenchHuntingIndex,
    DormancyVariance,
    FeatureEngineer,
    PartyDrivenDelayScore,
)


@dataclass(frozen=True)
class BaselineMetrics:
    """Population baseline statistics for deliberate delay features.

    These metrics are calculated from all resolved cases and serve as the
    reference point for Z-score standardization.

    Attributes:
        density_mean: Mean adjournment density across resolved cases.
        density_std: Standard deviation of adjournment density.
        party_score_mean: Mean party-driven delay score.
        party_score_std: Standard deviation of party-driven delay score.
        dormancy_cv_mean: Mean coefficient of variation in hearing gaps.
        dormancy_cv_std: Standard deviation of CV.
        bench_hunting_mean: Mean bench hunting pattern strength.
        bench_hunting_std: Standard deviation of pattern strength.
        sample_size: Number of resolved cases used for calculation.
        calculation_date: When these baselines were computed.
    """

    density_mean: float
    density_std: float
    party_score_mean: float
    party_score_std: float
    dormancy_cv_mean: float
    dormancy_cv_std: float
    bench_hunting_mean: float
    bench_hunting_std: float
    sample_size: int
    calculation_date: datetime


@dataclass(frozen=True)
class ZScores:
    """Standardized scores comparing case to population baseline.

    Z-score formula: (value - mean) / std_dev
    - Z-score = 0: Case exactly at baseline
    - Z-score > 0: Case above baseline (more concerning)
    - Z-score < 0: Case below baseline (less concerning)

    Attributes:
        density_z: Z-score for adjournment density.
        party_score_z: Z-score for party-driven delay score.
        dormancy_cv_z: Z-score for dormancy coefficient of variation.
        bench_hunting_z: Z-score for bench hunting pattern strength.
        composite_z: Weighted average of all z-scores.
    """

    density_z: float
    party_score_z: float
    dormancy_cv_z: float
    bench_hunting_z: float
    composite_z: float

    @property
    def extreme_scores(self) -> dict[str, float]:
        """Return only z-scores with |z| > 2 (extreme outliers)."""
        return {
            "density": self.density_z if abs(self.density_z) > 2 else None,
            "party_score": self.party_score_z if abs(self.party_score_z) > 2 else None,
            "dormancy_cv": self.dormancy_cv_z if abs(self.dormancy_cv_z) > 2 else None,
            "bench_hunting": self.bench_hunting_z if abs(self.bench_hunting_z) > 2 else None,
        }


@dataclass(frozen=True)
class DeliberateDelayProbability:
    """Final deliberate delay probability for a case.

    This combines all Phase 1, 2, and 3 analysis into a single probability
    score (0-100) indicating likelihood of systematic deliberate delays.

    Attributes:
        probability: Final score 0-100 (higher = more likely deliberate delay).
        percentile: Percentile rank among all cases (0-100).
        confidence: Confidence in the probability (0-1) based on data quality.
        risk_level: Categorical risk ('low', 'moderate', 'high', 'extreme').
        primary_drivers: List of factors most contributing to high probability.
        anomalies: List of z-scores > 2 standard deviations from baseline.
        explanation: Human-readable explanation of probability calculation.
    """

    probability: float
    percentile: float
    confidence: float
    risk_level: str
    primary_drivers: list[str]
    anomalies: list[str]
    explanation: str


class CaseAnomalyDetector:
    """Detects anomalies in cases compared to population baselines.

    This class computes baseline statistics from resolved cases and identifies
    cases that deviate significantly from expected patterns, indicating possible
    deliberate delay tactics.
    """

    # Z-score weights for composite calculation
    _DENSITY_WEIGHT = 0.25
    _PARTY_SCORE_WEIGHT = 0.35
    _DORMANCY_CV_WEIGHT = 0.20
    _BENCH_HUNTING_WEIGHT = 0.20

    # Percentile mapping for probability conversion
    # Maps composite z-score to probability (0-100)
    _PERCENTILE_TABLE = {
        -3.0: 0.1,
        -2.5: 0.6,
        -2.0: 2.3,
        -1.5: 6.7,
        -1.0: 15.9,
        -0.5: 30.9,
        0.0: 50.0,
        0.5: 69.1,
        1.0: 84.1,
        1.5: 93.3,
        2.0: 97.7,
        2.5: 99.4,
        3.0: 99.9,
    }

    @staticmethod
    def calculate_baselines(db: Session) -> BaselineMetrics:
        """Calculate population baseline metrics from all resolved cases.

        Args:
            db: SQLAlchemy database session.

        Returns:
            BaselineMetrics with mean and std for all features.

        Note:
            Only includes cases with status in common resolved states.
            Requires at least 3 resolved cases; returns zeros if insufficient data.
        """
        # Query all recent cases with hearings for baseline calculation
        # We use all available cases since is_disposed may not be reliably set
        resolved_cases = (
            db.query(Case)
            .order_by(Case.filing_date.desc())
            .limit(1000)  # Use up to 1000 recent cases for baseline
            .all()
        )

        if len(resolved_cases) < 3:
            # Insufficient data for meaningful statistics
            return BaselineMetrics(
                density_mean=0.0,
                density_std=0.0,
                party_score_mean=0.0,
                party_score_std=0.0,
                dormancy_cv_mean=0.0,
                dormancy_cv_std=0.0,
                bench_hunting_mean=0.0,
                bench_hunting_std=0.0,
                sample_size=len(resolved_cases),
                calculation_date=datetime.utcnow(),
            )

        # Calculate features for each resolved case
        densities = []
        party_scores = []
        dormancy_cvs = []
        bench_hunting_strengths = []

        for case in resolved_cases:
            try:
                # Phase 2 features
                density = FeatureEngineer.compute_adjournment_density(case, db)
                party_score = FeatureEngineer.compute_party_driven_delay_score(
                    case, db
                )
                dormancy = FeatureEngineer.compute_dormancy_variance(case, db)
                bench_hunting = FeatureEngineer.compute_bench_hunting_index(case, db)

                densities.append(density.density)
                party_scores.append(party_score.score)
                dormancy_cvs.append(dormancy.coefficient_of_variation)
                bench_hunting_strengths.append(bench_hunting.pattern_strength)

            except Exception:
                # Skip cases with calculation errors
                continue

        # Calculate statistics (need at least 2 data points for std dev)
        if len(densities) < 2:
            # Still insufficient data
            return BaselineMetrics(
                density_mean=0.0,
                density_std=0.0,
                party_score_mean=0.0,
                party_score_std=0.0,
                dormancy_cv_mean=0.0,
                dormancy_cv_std=0.0,
                bench_hunting_mean=0.0,
                bench_hunting_std=0.0,
                sample_size=0,
                calculation_date=datetime.utcnow(),
            )

        def safe_mean_std(values: list[float]) -> tuple[float, float]:
            """Calculate mean and std, handling edge cases."""
            if not values or len(values) < 2:
                return 0.0, 0.0
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            return mean, std

        density_mean, density_std = safe_mean_std(densities)
        party_mean, party_std = safe_mean_std(party_scores)
        dormancy_mean, dormancy_std = safe_mean_std(dormancy_cvs)
        bench_mean, bench_std = safe_mean_std(bench_hunting_strengths)

        return BaselineMetrics(
            density_mean=density_mean,
            density_std=density_std,
            party_score_mean=party_mean,
            party_score_std=party_std,
            dormancy_cv_mean=dormancy_mean,
            dormancy_cv_std=dormancy_std,
            bench_hunting_mean=bench_mean,
            bench_hunting_std=bench_std,
            sample_size=len(densities),
            calculation_date=datetime.utcnow(),
        )

    @staticmethod
    def compute_z_scores(
        case: Case,
        db: Session,
        baselines: BaselineMetrics,
    ) -> ZScores:
        """Compute Z-scores for a case against population baselines.

        Z-score = (value - mean) / std_dev

        Args:
            case: Case to analyze.
            db: SQLAlchemy database session.
            baselines: Population baseline metrics.

        Returns:
            ZScores with individual and composite z-scores.

        Note:
            If std_dev is 0 (no variation in population), z-score is set to 0.
        """
        # Calculate Phase 2 features
        density = FeatureEngineer.compute_adjournment_density(case, db)
        party_score = FeatureEngineer.compute_party_driven_delay_score(case, db)
        dormancy = FeatureEngineer.compute_dormancy_variance(case, db)
        bench_hunting = FeatureEngineer.compute_bench_hunting_index(case, db)

        def safe_z_score(value: float, mean: float, std: float) -> float:
            """Calculate z-score, handling zero standard deviation."""
            if std == 0:
                return 0.0
            return (value - mean) / std

        # Calculate individual z-scores
        density_z = safe_z_score(
            density.density, baselines.density_mean, baselines.density_std
        )
        party_score_z = safe_z_score(
            party_score.score, baselines.party_score_mean, baselines.party_score_std
        )
        dormancy_cv_z = safe_z_score(
            dormancy.coefficient_of_variation,
            baselines.dormancy_cv_mean,
            baselines.dormancy_cv_std,
        )
        bench_hunting_z = safe_z_score(
            bench_hunting.pattern_strength,
            baselines.bench_hunting_mean,
            baselines.bench_hunting_std,
        )

        # Calculate weighted composite z-score
        composite_z = (
            CaseAnomalyDetector._DENSITY_WEIGHT * density_z
            + CaseAnomalyDetector._PARTY_SCORE_WEIGHT * party_score_z
            + CaseAnomalyDetector._DORMANCY_CV_WEIGHT * dormancy_cv_z
            + CaseAnomalyDetector._BENCH_HUNTING_WEIGHT * bench_hunting_z
        )

        return ZScores(
            density_z=density_z,
            party_score_z=party_score_z,
            dormancy_cv_z=dormancy_cv_z,
            bench_hunting_z=bench_hunting_z,
            composite_z=composite_z,
        )

    @staticmethod
    def _interpolate_percentile(z_score: float) -> float:
        """Interpolate percentile from z-score using normal distribution CDF.

        Args:
            z_score: Standardized score (-4 to 4 typical range).

        Returns:
            Percentile (0-100) for this z-score.

        Note:
            Uses lookup table with linear interpolation between points.
            Clamps to [0.1, 99.9] to avoid extremes.
        """
        # Clamp z-score to table range
        z = max(-3.0, min(3.0, z_score))

        # Find surrounding entries
        table_keys = sorted(CaseAnomalyDetector._PERCENTILE_TABLE.keys())
        if z <= table_keys[0]:
            return CaseAnomalyDetector._PERCENTILE_TABLE[table_keys[0]]
        if z >= table_keys[-1]:
            return CaseAnomalyDetector._PERCENTILE_TABLE[table_keys[-1]]

        # Linear interpolation
        for i in range(len(table_keys) - 1):
            z1, z2 = table_keys[i], table_keys[i + 1]
            if z1 <= z <= z2:
                p1 = CaseAnomalyDetector._PERCENTILE_TABLE[z1]
                p2 = CaseAnomalyDetector._PERCENTILE_TABLE[z2]
                # Linear interpolation
                frac = (z - z1) / (z2 - z1)
                return p1 + frac * (p2 - p1)

        return 50.0

    @staticmethod
    def compute_probability(
        case: Case,
        db: Session,
        baselines: Optional[BaselineMetrics] = None,
    ) -> DeliberateDelayProbability:
        """Compute final deliberate delay probability for a case.

        Args:
            case: Case to analyze.
            db: SQLAlchemy database session.
            baselines: Pre-calculated population baselines. If None, will be calculated.

        Returns:
            DeliberateDelayProbability with final score and risk assessment.
        """
        # Calculate or use provided baselines
        if baselines is None:
            baselines = CaseAnomalyDetector.calculate_baselines(db)

        # Get Phase 2 features
        density = FeatureEngineer.compute_adjournment_density(case, db)
        party_score = FeatureEngineer.compute_party_driven_delay_score(case, db)
        dormancy = FeatureEngineer.compute_dormancy_variance(case, db)
        bench_hunting = FeatureEngineer.compute_bench_hunting_index(case, db)

        # Compute z-scores
        z_scores = CaseAnomalyDetector.compute_z_scores(case, db, baselines)

        # Convert composite z-score to percentile (0-100)
        percentile = CaseAnomalyDetector._interpolate_percentile(z_scores.composite_z)

        # Calculate confidence based on data quality
        # Confidence decreases with fewer hearings (low data quality)
        hearings = db.query(Hearing).filter(Hearing.case_id == case.id).count()
        confidence = min(1.0, max(0.3, hearings / 20.0))  # 0.3-1.0 range

        # Identify anomalies (z-score > 2 standard deviations)
        anomalies = []
        if abs(z_scores.density_z) > 2:
            anomalies.append(
                f"Adjournment density {density.density:.1f}% "
                f"(z={z_scores.density_z:.2f})"
            )
        if abs(z_scores.party_score_z) > 2:
            anomalies.append(
                f"Party-driven delay score {party_score.score:.1f} "
                f"(z={z_scores.party_score_z:.2f})"
            )
        if abs(z_scores.dormancy_cv_z) > 2:
            anomalies.append(
                f"Dormancy variability CV {dormancy.coefficient_of_variation:.3f} "
                f"(z={z_scores.dormancy_cv_z:.2f})"
            )
        if abs(z_scores.bench_hunting_z) > 2:
            anomalies.append(
                f"Bench hunting pattern strength {bench_hunting.pattern_strength:.3f} "
                f"(z={z_scores.bench_hunting_z:.2f})"
            )

        # Identify primary drivers (top factors contributing to high probability)
        primary_drivers = []
        scores_with_weights = [
            ("Adjournment density", z_scores.density_z, CaseAnomalyDetector._DENSITY_WEIGHT),
            ("Party-driven tactics", z_scores.party_score_z, CaseAnomalyDetector._PARTY_SCORE_WEIGHT),
            ("Dormancy variability", z_scores.dormancy_cv_z, CaseAnomalyDetector._DORMANCY_CV_WEIGHT),
            ("Bench hunting pattern", z_scores.bench_hunting_z, CaseAnomalyDetector._BENCH_HUNTING_WEIGHT),
        ]
        # Sort by weighted z-score (absolute value)
        scores_sorted = sorted(
            scores_with_weights,
            key=lambda x: abs(x[1]) * x[2],
            reverse=True,
        )
        for name, z, weight in scores_sorted[:2]:  # Top 2 drivers
            if abs(z) > 0.5:  # Only include if meaningful
                primary_drivers.append(name)

        # Determine risk level based on percentile
        if percentile < 30:
            risk_level = "low"
        elif percentile < 60:
            risk_level = "moderate"
        elif percentile < 85:
            risk_level = "high"
        else:
            risk_level = "extreme"

        # Build explanation
        explanation = (
            f"Case {case.case_number} deliberate delay probability: {percentile:.1f}th percentile "
            f"(composite z-score: {z_scores.composite_z:.2f}). "
            f"Adjournment density: {density.density:.1f}% (baseline: {baselines.density_mean:.1f}%). "
            f"Party delay score: {party_score.score:.1f}/100 (baseline: {baselines.party_score_mean:.1f}). "
            f"Risk level: {risk_level.upper()}."
        )
        if primary_drivers:
            explanation += f" Primary drivers: {', '.join(primary_drivers)}."

        return DeliberateDelayProbability(
            probability=percentile,
            percentile=percentile,
            confidence=confidence,
            risk_level=risk_level,
            primary_drivers=primary_drivers,
            anomalies=anomalies,
            explanation=explanation,
        )
