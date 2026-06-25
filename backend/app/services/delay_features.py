"""
Phase 2: Delay Feature Engineering Service

Extracts and computes 4 key features for baseline deviation analysis:
1. Adjournment Density - Rate of adjournments vs total hearings
2. Party-Driven Delay Score - % of party-requested adjournments
3. Dormancy Variance - Variance in gap patterns between hearings
4. Bench Hunting Index - Court/judge shopping measure
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import Adjournment, Case, CourtAnalyticalSnapshot, Hearing, HearingOutcomeType
from app.models.entities import AdjournmentReasonType
from app.schemas.delay_features import (
    AdjournmentDensityMetrics,
    BenchHuntingLevel,
    BenchHuntingMetrics,
    CaseDelayFeatures,
    DelayScoreLevel,
    DormancyVarianceMetrics,
    FeatureExtractionResult,
    PartyDrivenDelayMetrics,
)

logger = logging.getLogger(__name__)


class DelayFeatureExtractor:
    """Extract delay features from case data for baseline deviation analysis."""

    # Thresholds for categorization
    PARTY_DELAY_THRESHOLDS = {
        DelayScoreLevel.LOW: (0, 40),
        DelayScoreLevel.MODERATE: (40, 70),
        DelayScoreLevel.HIGH: (70, 85),
        DelayScoreLevel.EXTREME: (85, 100),
    }

    # Bench hunting score mapping
    BENCH_HUNTING_SCORE_MAPPING = {
        1: (BenchHuntingLevel.NO_HUNTING, (0.0, 1.5)),
        2: (BenchHuntingLevel.MINIMAL, (1.5, 3.0)),
        3: (BenchHuntingLevel.MODERATE, (3.0, 5.0)),
        5: (BenchHuntingLevel.SIGNIFICANT, (5.0, 7.5)),
        10: (BenchHuntingLevel.EXTENSIVE, (7.5, 10.0)),
    }

    def __init__(self, db: Session):
        """Initialize extractor with database session."""
        self.db = db

    def _get_court_snapshot(self, court_id: int | None) -> CourtAnalyticalSnapshot | None:
        if court_id is None:
            return None
        return (
            self.db.query(CourtAnalyticalSnapshot)
            .filter(CourtAnalyticalSnapshot.court_id == court_id)
            .first()
        )

    @staticmethod
    def _is_irregular_gap_pattern(
        *,
        mean_gap: float,
        cv: float,
        snapshot: CourtAnalyticalSnapshot | None,
        population_median_cv: float | None,
    ) -> bool:
        if snapshot is not None:
            median_gap_baseline = max(0.0, float(snapshot.median_time_between_hearings_days))
            if median_gap_baseline > 0:
                return mean_gap > (median_gap_baseline * 1.5)
            return cv > 0.8

        baseline_cv = 0.5 if population_median_cv is None else population_median_cv
        return cv > baseline_cv

    # ========== FEATURE 1: Adjournment Density ==========

    def extract_adjournment_density(
        self, case_id: int, population_mean: Optional[float] = None, population_std_dev: Optional[float] = None
    ) -> AdjournmentDensityMetrics:
        """
        Calculate adjournment density for a case.

        Density = (adjournments / total_hearings) * 100

        Args:
            case_id: ID of case to analyze
            population_mean: Population mean for z-score calculation (if None, calculated)
            population_std_dev: Population std dev for z-score (if None, calculated)

        Returns:
            AdjournmentDensityMetrics with density and outlier status
        """
        # Get case hearings and adjournments
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # Query total hearings
        total_hearings = (
            self.db.query(func.count(Hearing.id))
            .filter(Hearing.case_id == case_id)
            .scalar() or 0
        )

        # Query adjournments
        total_adjournments = (
            self.db.query(func.count(Adjournment.id))
            .filter(
                and_(
                    Adjournment.case_id == case_id,
                    Adjournment.is_adjournment == True,
                )
            )
            .scalar() or 0
        )

        # Calculate density
        density_percentage = 0.0
        if total_hearings > 0:
            density_percentage = (total_adjournments / total_hearings) * 100

        snapshot = self._get_court_snapshot(case.court_id)
        if population_mean is None:
            population_mean = snapshot.mean_adjournment_rate if snapshot is not None else 0.0
        if population_std_dev is None:
            population_std_dev = snapshot.std_dev_adjournment_rate if snapshot is not None else 0.0

        # Calculate z-score
        z_score = 0.0
        if population_std_dev > 0:
            z_score = (density_percentage - population_mean) / population_std_dev

        # Determine outlier status (> mean + 2*std_dev)
        is_outlier = density_percentage > (population_mean + 2 * population_std_dev)

        if snapshot is None:
            logger.warning("Court analytical snapshot missing for case_id=%s court_id=%s", case_id, case.court_id)

        return AdjournmentDensityMetrics(
            case_id=case_id,
            total_hearings=total_hearings,
            total_adjournments=total_adjournments,
            density_percentage=density_percentage,
            population_mean=population_mean,
            population_std_dev=population_std_dev,
            z_score=z_score,
            is_outlier=is_outlier,
        )

    # ========== FEATURE 2: Party-Driven Delay Score ==========

    def extract_party_driven_delay(self, case_id: int) -> PartyDrivenDelayMetrics:
        """
        Calculate party-driven delay score.

        % = (party_requested_adjournments / total_adjournments) * 100

        Args:
            case_id: ID of case to analyze

        Returns:
            PartyDrivenDelayMetrics with percentages and contributing advocates
        """
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # Get all adjournments for this case
        adjournments = (
            self.db.query(Adjournment)
            .filter(
                and_(
                    Adjournment.case_id == case_id,
                    Adjournment.is_adjournment == True,
                )
            )
            .all()
        )

        total_adjournments = len(adjournments)
        party_requested = 0
        court_requested = 0
        advocate_contributions = {}

        for adj in adjournments:
            # Party-requested: ON_REQUEST reason type or requested_by field set
            is_party_requested = (
                adj.reason_type == AdjournmentReasonType.ON_REQUEST
                or adj.reason_type == AdjournmentReasonType.PARTY_NOT_READY
                or adj.reason_type == AdjournmentReasonType.COUNSEL_UNAVAILABLE
                or adj.requested_by is not None
            )

            if is_party_requested:
                party_requested += 1
                if adj.requested_by:
                    advocate_contributions[adj.requested_by] = (
                        advocate_contributions.get(adj.requested_by, 0) + 1
                    )
            else:
                court_requested += 1

        # Calculate percentage
        party_request_percentage = 0.0
        if total_adjournments > 0:
            party_request_percentage = (party_requested / total_adjournments) * 100

        # Determine level
        level = self._categorize_party_delay(party_request_percentage)

        return PartyDrivenDelayMetrics(
            case_id=case_id,
            total_adjournments=total_adjournments,
            party_requested_adjournments=party_requested,
            court_requested_adjournments=court_requested,
            party_request_percentage=party_request_percentage,
            level=level,
            contributing_advocates=advocate_contributions,
        )

    def _categorize_party_delay(self, percentage: float) -> DelayScoreLevel:
        """Categorize party delay percentage into level."""
        for level, (low, high) in self.PARTY_DELAY_THRESHOLDS.items():
            if low <= percentage < high:
                return level
        return DelayScoreLevel.EXTREME

    # ========== FEATURE 3: Dormancy Variance ==========

    def extract_dormancy_variance(
        self, case_id: int, population_median_cv: Optional[float] = None
    ) -> DormancyVarianceMetrics:
        """
        Calculate dormancy variance - measure of irregular gap patterns.

        High variance with low mean suggests deliberate sporadic delays.
        Coefficient of Variation = std_dev / mean (normalized measure)

        Args:
            case_id: ID of case to analyze
            population_median_cv: Median coefficient of variation in population

        Returns:
            DormancyVarianceMetrics with gap analysis
        """
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        # Get all hearings in chronological order
        hearings = (
            self.db.query(Hearing.date)
            .filter(Hearing.case_id == case_id)
            .order_by(Hearing.date)
            .all()
        )

        # Calculate gaps between consecutive hearings
        gaps = []
        if len(hearings) >= 2:
            for i in range(1, len(hearings)):
                gap_days = (hearings[i][0] - hearings[i - 1][0]).days
                if gap_days >= 0:  # Only positive gaps
                    gaps.append(gap_days)

        # Calculate statistics
        if gaps:
            min_gap = min(gaps)
            max_gap = max(gaps)
            mean_gap = sum(gaps) / len(gaps)
            variance = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            std_dev = math.sqrt(variance)
            cv = (std_dev / mean_gap) if mean_gap > 0 else 0.0
        else:
            min_gap = max_gap = 0
            mean_gap = 0.0
            variance = 0.0
            std_dev = 0.0
            cv = 0.0

        snapshot = self._get_court_snapshot(case.court_id)
        is_irregular = self._is_irregular_gap_pattern(
            mean_gap=mean_gap,
            cv=cv,
            snapshot=snapshot,
            population_median_cv=population_median_cv,
        )

        return DormancyVarianceMetrics(
            case_id=case_id,
            hearing_gaps_days=gaps,
            min_gap_days=int(min_gap),
            max_gap_days=int(max_gap),
            mean_gap_days=round(mean_gap, 2),
            variance=round(variance, 2),
            std_dev_days=round(std_dev, 2),
            coefficient_of_variation=round(cv, 3),
            is_irregular_pattern=is_irregular,
        )

    # ========== FEATURE 4: Bench Hunting Index ==========

    def extract_bench_hunting(self, case_id: int) -> BenchHuntingMetrics:
        """
        Calculate bench hunting index - measure of forum shopping.

        Based on:
        - Number of distinct courts used
        - Number of bench changes in same court
        - Frequency of changes

        Args:
            case_id: ID of case to analyze

        Returns:
            BenchHuntingMetrics with hunting score and level
        """
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        primary_court_id = case.court_id

        # Get all distinct courts in case hearings
        # Get distinct courts (in this case, just the one)
        unique_courts = set()
        unique_courts.add(primary_court_id)

        # For now, bench hunting is primarily based on court count
        # In a more sophisticated system, this would track actual related matters
        unique_courts_count = len(unique_courts)

        # Count bench changes (hearings with different judges sequentially)
        bench_changes = self._count_bench_changes(case_id)

        # Calculate hunting index (0-10 scale)
        # Base: unique courts contribute more
        # Additional: bench changes indicate forum manipulation
        hunting_index = 0.0
        indicators = []

        if unique_courts_count > 1:
            hunting_index += min(3.0 * (unique_courts_count - 1), 6.0)
            indicators.append(f"multiple_courts_{unique_courts_count}")

        if bench_changes > 3:
            hunting_index += min(2.0 * (bench_changes / 10), 3.0)
            indicators.append(f"frequent_bench_changes_{bench_changes}")

        hunting_index = min(hunting_index, 10.0)

        # Categorize level
        level = self._categorize_bench_hunting(hunting_index)

        return BenchHuntingMetrics(
            case_id=case_id,
            primary_court_id=primary_court_id,
            unique_courts_used=unique_courts,
            unique_courts_count=unique_courts_count,
            bench_changes=bench_changes,
            hunting_index=round(hunting_index, 1),
            level=level,
            indicators=indicators,
        )

    def _count_bench_changes(self, case_id: int) -> int:
        """Count number of bench changes in case hearings."""
        hearings = (
            self.db.query(Hearing.judge_id)
            .filter(Hearing.case_id == case_id)
            .order_by(Hearing.date)
            .all()
        )

        if len(hearings) <= 1:
            return 0

        changes = 0
        for i in range(1, len(hearings)):
            if hearings[i][0] != hearings[i - 1][0]:
                changes += 1

        return changes

    def _categorize_bench_hunting(self, index: float) -> BenchHuntingLevel:
        """Categorize hunting index into level."""
        if index < 1.5:
            return BenchHuntingLevel.NO_HUNTING
        elif index < 3.0:
            return BenchHuntingLevel.MINIMAL
        elif index < 5.0:
            return BenchHuntingLevel.MODERATE
        elif index < 7.5:
            return BenchHuntingLevel.SIGNIFICANT
        else:
            return BenchHuntingLevel.EXTENSIVE

    # ========== MAIN EXTRACTION METHOD ==========

    def extract_all_features(self, case_id: int) -> CaseDelayFeatures:
        """
        Extract all delay features for a case.

        Args:
            case_id: ID of case to analyze

        Returns:
            CaseDelayFeatures with all 4 feature sets
        """
        try:
            adjournment_density = self.extract_adjournment_density(case_id)
            party_driven_delay = self.extract_party_driven_delay(case_id)
            dormancy_variance = self.extract_dormancy_variance(case_id)
            bench_hunting = self.extract_bench_hunting(case_id)

            return CaseDelayFeatures(
                case_id=case_id,
                adjournment_density=adjournment_density,
                party_driven_delay=party_driven_delay,
                dormancy_variance=dormancy_variance,
                bench_hunting=bench_hunting,
            )
        except Exception:
            logger.exception("Error extracting features for case %s", case_id)
            raise

    def extract_batch_features(self, case_ids: list[int]) -> FeatureExtractionResult:
        """
        Extract features for multiple cases in batch.

        Args:
            case_ids: List of case IDs to process

        Returns:
            FeatureExtractionResult with success/failure counts and features
        """
        start_time = time.time()
        features = []
        error_cases = []
        successful = 0
        failed = 0

        for case_id in case_ids:
            try:
                feature_set = self.extract_all_features(case_id)
                features.append(feature_set)
                successful += 1
            except Exception as e:
                error_cases.append({"case_id": case_id, "error_message": str(e)})
                failed += 1
                logger.warning(f"Failed to extract features for case {case_id}: {e}")

        processing_time = time.time() - start_time

        return FeatureExtractionResult(
            total_cases=len(case_ids),
            successful=successful,
            failed=failed,
            error_cases=error_cases,
            processing_time_seconds=round(processing_time, 2),
            features=features,
        )
