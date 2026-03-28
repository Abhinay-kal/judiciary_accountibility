"""REST API endpoints for Deliberate Delay Detection (Phases 1-3).

This module provides the following endpoints:

GET /api/v1/delay-detection/health
    Health check for the delay detection system

GET /api/v1/delay-detection/baseline
    Calculate or retrieve population baseline metrics

GET /api/v1/delay-detection/case/{case_id}
    Analyze a single case for deliberate delay probability

POST /api/v1/delay-detection/batch
    Batch analyze multiple cases

GET /api/v1/delay-detection/case/{case_id}/features
    Get the extracted features for a case (for debugging)
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.deliberate_delay import (
    BaselineMetricsResponse,
    BatchDelayAnalysisResponse,
    CaseProbabilityAnalysis,
    CaseFeatureValues,
    DelayProbabilityResponse,
    ErrorResponse,
    HealthCheckResponse,
    ZScoresResponse,
)

router = APIRouter(prefix="/delay-detection", tags=["delay-detection"])


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Check if delay detection system is operational.

    Returns:
        HealthCheckResponse with status of all three phases and baseline availability.
    """
    try:
        from app.services.adjournment import classify_adjournment_tactic
        from app.services.delay_detection_phase2 import FeatureEngineer
        from app.services.delay_detection_phase3 import CaseAnomalyDetector
        from app.db.population_cache import PopulationCache

        # Check Phase 1
        try:
            classify_adjournment_tactic("test")
            phase1_available = True
        except Exception:
            phase1_available = False

        # Check Phase 2
        try:
            FeatureEngineer()
            phase2_available = True
        except Exception:
            phase2_available = False

        # Check Phase 3
        try:
            CaseAnomalyDetector()
            phase3_available = True
        except Exception:
            phase3_available = False

        # Check baseline cache
        try:
            cache = PopulationCache(db)
            baseline = cache.get_baseline_metrics()
            baseline_available = baseline is not None
            baseline_sample_size = baseline.sample_size if baseline else None
            baseline_last_updated = baseline.calculation_date if baseline else None
        except Exception:
            baseline_available = False
            baseline_sample_size = None
            baseline_last_updated = None

        # Determine overall status
        if phase1_available and phase2_available and phase3_available:
            status = "healthy" if baseline_available else "degraded"
        else:
            status = "error"

        return HealthCheckResponse(
            status=status,
            phase1_available=phase1_available,
            phase2_available=phase2_available,
            phase3_available=phase3_available,
            baseline_available=baseline_available,
            baseline_sample_size=baseline_sample_size,
            baseline_last_updated=baseline_last_updated,
            message="All systems operational"
            if status == "healthy"
            else "Baseline metrics not yet calculated"
            if status == "degraded"
            else "One or more phases unavailable",
        )

    except Exception as e:
        return HealthCheckResponse(
            status="error",
            phase1_available=False,
            phase2_available=False,
            phase3_available=False,
            baseline_available=False,
            message=f"Health check failed: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Baseline Metrics Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/baseline",
    response_model=BaselineMetricsResponse,
    responses={
        200: {"description": "Baseline successfully retrieved or calculated"},
        202: {"description": "Baseline calculation in progress"},
        500: {"description": "Baseline calculation failed"},
    },
)
def get_baseline_metrics(
    recalculate: bool = Query(
        False,
        description="Force recalculation of baseline from database",
    ),
    db: Session = Depends(get_db),
) -> BaselineMetricsResponse:
    """Get population baseline metrics for anomaly detection.

    The baseline is calculated from all resolved cases and cached. On first call,
    it is calculated automatically. Use `recalculate=true` to force recalculation
    (useful after new cases are disposed).

    Args:
        recalculate: If True, force recalculation from database
        db: Database session

    Returns:
        BaselineMetricsResponse with mean and std for all 4 features

    Raises:
        HTTPException(502): If baseline calculation fails
    """
    try:
        from app.db.population_cache import PopulationCache
        from app.services.delay_detection_phase3 import CaseAnomalyDetector

        cache = PopulationCache(db)

        # Check if we should recalculate
        if recalculate or cache.get_baseline_metrics() is None:
            detector = CaseAnomalyDetector()
            baseline = detector.calculate_baselines(db)
            cache.set_baseline_metrics(baseline)
        else:
            baseline = cache.get_baseline_metrics()

        if baseline is None:
            return BaselineMetricsResponse(
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
                status="error",
                message="No resolved cases available to calculate baseline",
            )

        return BaselineMetricsResponse(
            density_mean=baseline.density_mean,
            density_std=baseline.density_std,
            party_score_mean=baseline.party_score_mean,
            party_score_std=baseline.party_score_std,
            dormancy_cv_mean=baseline.dormancy_cv_mean,
            dormancy_cv_std=baseline.dormancy_cv_std,
            bench_hunting_mean=baseline.bench_hunting_mean,
            bench_hunting_std=baseline.bench_hunting_std,
            sample_size=baseline.sample_size,
            calculation_date=baseline.calculation_date,
            status="success",
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to calculate baseline metrics: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Single Case Analysis Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/case/{case_id}",
    response_model=DelayProbabilityResponse,
    responses={
        200: {"description": "Case successfully analyzed"},
        404: {"description": "Case not found"},
        422: {"description": "Case is not a valid litigation case"},
        502: {"description": "Analysis failed"},
    },
)
def analyze_case_delay(
    case_id: int,
    db: Session = Depends(get_db),
) -> DelayProbabilityResponse:
    """Analyze a single case for deliberate delay probability.

    Runs the complete Phase 1→2→3 pipeline:
    1. Phase 1: Classify adjournment tactics from hearing outcomes
    2. Phase 2: Extract and combine delay-related features
    3. Phase 3: Compare against population baseline and compute probability

    Args:
        case_id: The case ID to analyze
        db: Database session

    Returns:
        DelayProbabilityResponse with probability (0-100), risk level, and explanation

    Raises:
        HTTPException(404): If case not found
        HTTPException(422): If case has no hearing outcomes
        HTTPException(502): If analysis fails
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Rollback any previous failed transaction
        db.rollback()
        
        from sqlalchemy import func

        from app.db.population_cache import PopulationCache
        from app.db.session import SessionLocal
        from app.models import Case, Hearing
        from app.services.adjournment import classify_adjournment_tactic
        from app.services.delay_detection_phase2 import FeatureEngineer
        from app.services.delay_detection_phase3 import CaseAnomalyDetector

        logger.info(f"Analyzing case {case_id}")
        
        # ── Validate case exists ──────────────────────────────────────────────
        logger.info("Querying case...")
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None or case.is_deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Case with ID {case_id} not found",
            )

        # ── Check for hearings ────────────────────────────────────────────────
        logger.info("Counting hearings...")
        hearing_count = db.query(func.count(Hearing.id)).filter(
            Hearing.case_id == case_id
        ).scalar()

        if hearing_count == 0:
            return DelayProbabilityResponse(
                case_id=case_id,
                case_number=case.case_number,
                probability=0.0,
                percentile=0.0,
                risk_level="low",
                confidence=0.3,
                primary_drivers=[],
                anomalies=[],
                explanation="Case has no hearing outcomes. Cannot assess delay patterns.",
                analysis_timestamp=datetime.utcnow(),
                status="error",
            )

        # ── Phase 1: Classify adjournment tactics ─────────────────────────────
        logger.info("Fetching hearings for Phase 1...")
        hearings = db.query(Hearing).filter(Hearing.case_id == case_id).all()
        tactic_frequencies = {}

        for hearing in hearings:
            if hearing.outcome_text:
                result = classify_adjournment_tactic(hearing.outcome_text)
                tactic_name = result.tactic.value
                tactic_frequencies[tactic_name] = (
                    tactic_frequencies.get(tactic_name, 0) + 1
                )

        # ── Phase 2: Extract features ────────────────────────────────────────
        # ── Phase 3: Calculate probability ───────────────────────────────────
        detector = CaseAnomalyDetector()
        cache = PopulationCache(db)
        baseline = cache.get_baseline_metrics()

        if baseline is None:
            try:
                # Use separate session for baseline calculation to avoid transaction issues
                baseline_db = SessionLocal()
                try:
                    baseline = detector.calculate_baselines(baseline_db)
                    cache.set_baseline_metrics(baseline)
                finally:
                    baseline_db.close()
            except Exception as calc_error:
                # If baseline calc fails, use default baseline with zeros
                from app.services.delay_detection_phase3 import BaselineMetrics

                baseline = BaselineMetrics(
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
                # Log the error but continue
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Baseline calculation failed: {str(calc_error)[:100]}")

        # Compute z-scores for debugging
        z_scores = detector.compute_z_scores(case, db, baseline)

        # Compute final probability (will recalculate features and z-scores)
        probability = detector.compute_probability(case, db, baseline)

        return DelayProbabilityResponse(
            case_id=case_id,
            case_number=case.case_number,
            probability=probability.probability,
            percentile=probability.percentile,
            risk_level=probability.risk_level,
            confidence=probability.confidence,
            primary_drivers=probability.primary_drivers,
            anomalies=probability.anomalies,
            explanation=probability.explanation,
            analysis_timestamp=datetime.utcnow(),
            status="success",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to analyze case: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Case Features Endpoint (Debugging)
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/case/{case_id}/features",
    response_model=CaseFeatureValues,
    responses={
        200: {"description": "Features successfully extracted"},
        404: {"description": "Case not found"},
        502: {"description": "Feature extraction failed"},
    },
)
def get_case_features(
    case_id: int,
    db: Session = Depends(get_db),
) -> CaseFeatureValues:
    """Get the extracted Phase 2 features for a case (for debugging/inspection).

    Returns the four features used in the delay probability calculation:
    - adjournment_density: Adjournments per day of case life
    - party_driven_score: Estimated party-driven delay tactics (0-4)
    - dormancy_cv: Coefficient of variation in delays
    - bench_hunting_index: Pattern of judge-switching (0-1)

    Args:
        case_id: The case ID
        db: Database session

    Returns:
        CaseFeatureValues with all extracted features

    Raises:
        HTTPException(404): If case not found
        HTTPException(502): If feature extraction fails
    """
    try:
        from app.models import Case
        from app.services.delay_detection_phase2 import FeatureEngineer

        # Validate case
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None or case.is_deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Case with ID {case_id} not found",
            )

        # Extract features
        feature_engineer = FeatureEngineer()
        features = feature_engineer.engineer(case, db)

        return CaseFeatureValues(
            case_id=case_id,
            case_number=case.case_number,
            adjournment_density=features.adjournment_density,
            party_driven_score=features.party_score,
            dormancy_cv=features.dormancy_cv,
            bench_hunting_index=features.bench_hunting_index,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to extract features: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Batch Analysis Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/batch",
    response_model=BatchDelayAnalysisResponse,
    responses={
        200: {"description": "Batch analysis completed"},
        400: {"description": "Invalid case IDs"},
        502: {"description": "Batch analysis failed"},
    },
)
def batch_analyze_cases(
    case_ids: List[int] = Query(
        ...,
        description="List of case IDs to analyze",
        min_items=1,
        max_items=1000,
    ),
    db: Session = Depends(get_db),
) -> BatchDelayAnalysisResponse:
    """Batch analyze multiple cases for deliberate delay probability.

    Analyzes up to 1000 cases in a single request. Returns summary statistics
    and individual results for each case.

    Args:
        case_ids: List of case IDs to analyze (1-1000 cases)
        db: Database session

    Returns:
        BatchDelayAnalysisResponse with individual results and aggregate statistics

    Raises:
        HTTPException(400): If case_ids is invalid
        HTTPException(502): If batch analysis fails
    """
    if not case_ids:
        raise HTTPException(
            status_code=400,
            detail="case_ids list cannot be empty",
        )

    if len(case_ids) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Maximum 1000 cases per batch request",
        )

    try:
        # Rollback any previous failed transaction
        db.rollback()
        
        from app.db.population_cache import PopulationCache
        from app.db.session import SessionLocal
        from app.models import Case
        from app.services.delay_detection_phase3 import CaseAnomalyDetector
        from app.services.delay_detection_phase2 import FeatureEngineer
        from app.services.adjournment import classify_adjournment_tactic

        # Prepare baseline
        cache = PopulationCache(db)
        baseline = cache.get_baseline_metrics()

        if baseline is None:
            try:
                # Use separate session for baseline calculation
                baseline_db = SessionLocal()
                try:
                    detector = CaseAnomalyDetector()
                    baseline = detector.calculate_baselines(baseline_db)
                    cache.set_baseline_metrics(baseline)
                finally:
                    baseline_db.close()
            except Exception:
                # If baseline calc fails, use default baseline
                from app.services.delay_detection_phase3 import BaselineMetrics
                baseline = BaselineMetrics(
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

        # Analyze cases
        results: List[CaseProbabilityAnalysis] = []
        probabilities_list: List[float] = []
        error_count = 0

        for case_id in case_ids:
            try:
                case = (
                    db.query(Case)
                    .filter(Case.id == case_id, Case.is_deleted == False)
                    .first()
                )

                if case is None:
                    error_count += 1
                    continue

                # Compute probability
                detector = CaseAnomalyDetector()
                z_scores = detector.compute_z_scores(case, db, baseline)
                probability_result = detector.compute_probability(case, db, baseline)

                results.append(
                    CaseProbabilityAnalysis(
                        case_id=case_id,
                        case_number=case.case_number,
                        probability=probability_result.probability,
                        risk_level=probability_result.risk_level,
                        confidence=probability_result.confidence,
                        primary_drivers=probability_result.primary_drivers,
                    )
                )

                probabilities_list.append(probability_result.probability)

            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error analyzing case {case_id}: {str(e)[:200]}")
                error_count += 1
                continue

        # Compute summary statistics
        summary_stats = {}
        if probabilities_list:
            from statistics import mean, stdev

            summary_stats = {
                "count": len(probabilities_list),
                "mean": mean(probabilities_list),
                "min": min(probabilities_list),
                "max": max(probabilities_list),
                "median": sorted(probabilities_list)[
                    len(probabilities_list) // 2
                ],
            }

            if len(probabilities_list) > 1:
                summary_stats["stdev"] = stdev(probabilities_list)

        return BatchDelayAnalysisResponse(
            analysis_type="batch_delay_analysis",
            total_cases_analyzed=len(case_ids),
            success_count=len(results),
            error_count=error_count,
            results=results,
            summary_stats=summary_stats,
            analysis_timestamp=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Batch analysis failed: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Z-Scores Endpoint (Advanced: for monitoring/debugging)
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/case/{case_id}/z-scores",
    response_model=ZScoresResponse,
    responses={
        200: {"description": "Z-scores successfully computed"},
        404: {"description": "Case not found"},
        502: {"description": "Z-score computation failed"},
    },
)
def get_case_z_scores(
    case_id: int,
    db: Session = Depends(get_db),
) -> ZScoresResponse:
    """Get the standardized z-scores for a case (advanced/debugging).

    Z-scores show how many standard deviations each feature deviates from
    the population mean. Useful for understanding which features are anomalous.

    |z| > 2 indicates a statistical anomaly (outside 95% confidence interval)

    Args:
        case_id: The case ID
        db: Database session

    Returns:
        ZScoresResponse with individual and composite z-scores

    Raises:
        HTTPException(404): If case not found
        HTTPException(502): If computation fails
    """
    try:
        from app.db.population_cache import PopulationCache
        from app.models import Case
        from app.services.delay_detection_phase2 import FeatureEngineer
        from app.services.delay_detection_phase3 import CaseAnomalyDetector

        # Validate case
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None or case.is_deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Case with ID {case_id} not found",
            )

        # Get baseline
        cache = PopulationCache(db)
        baseline = cache.get_baseline_metrics()

        if baseline is None:
            detector = CaseAnomalyDetector()
            baseline = detector.calculate_baselines(db)
            cache.set_baseline_metrics(baseline)

        detector = CaseAnomalyDetector()
        z_scores = detector.compute_z_scores(case, db, baseline)

        return ZScoresResponse(
            density_z=z_scores.density_z,
            party_score_z=z_scores.party_score_z,
            dormancy_cv_z=z_scores.dormancy_cv_z,
            bench_hunting_z=z_scores.bench_hunting_z,
            composite_z=z_scores.composite_z,
            anomalies=z_scores.anomalies,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to compute z-scores: {str(e)}",
        )
