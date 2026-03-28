"""Pydantic schemas for Deliberate Delay Detection API responses.

This module defines the response schemas for:
- Baseline metrics calculation
- Z-score computation  
- Probability scoring
- Batch analysis
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Field descriptions
CASE_IDENTIFIER_DESC = "Case identifier"


# ─────────────────────────────────────────────────────────────────────────────
# Individual Component Schemas
# ─────────────────────────────────────────────────────────────────────────────


class BaselineMetricsResponse(BaseModel):
    """Response for baseline metrics calculation from resolved cases."""

    density_mean: float = Field(
        ..., description="Mean adjournment density across resolved cases"
    )
    density_std: float = Field(
        ..., description="Standard deviation of adjournment density"
    )
    party_score_mean: float = Field(
        ..., description="Mean party-driven delay score across resolved cases"
    )
    party_score_std: float = Field(
        ..., description="Standard deviation of party-driven delay score"
    )
    dormancy_cv_mean: float = Field(
        ...,
        description="Mean dormancy coefficient of variation across resolved cases",
    )
    dormancy_cv_std: float = Field(
        ..., description="Standard deviation of dormancy coefficient of variation"
    )
    bench_hunting_mean: float = Field(
        ..., description="Mean bench hunting index across resolved cases"
    )
    bench_hunting_std: float = Field(
        ..., description="Standard deviation of bench hunting index"
    )
    sample_size: int = Field(
        ...,
        description="Number of resolved cases used to calculate baseline",
    )
    calculation_date: datetime = Field(
        ..., description="When the baseline was calculated"
    )
    status: str = Field(
        default="success",
        description="Status of baseline calculation (success or error)",
    )
    message: Optional[str] = Field(
        default=None, description="Additional message or error details"
    )

    model_config = ConfigDict(from_attributes=True)


class ZScoresResponse(BaseModel):
    """Response for z-score computation against baseline."""

    density_z: float = Field(
        ..., description="Z-score for adjournment density (standardized deviation)"
    )
    party_score_z: float = Field(
        ..., description="Z-score for party-driven delay score"
    )
    dormancy_cv_z: float = Field(
        ..., description="Z-score for dormancy coefficient of variation"
    )
    bench_hunting_z: float = Field(
        ..., description="Z-score for bench hunting index"
    )
    composite_z: float = Field(
        ...,
        description="Weighted composite z-score combining all four features",
    )
    anomalies: List[str] = Field(
        default_factory=list,
        description="List of features with |z| > 2 (statistical anomalies)",
    )

    model_config = ConfigDict(from_attributes=True)


class RiskLevelStats(BaseModel):
    """Statistics for a specific risk level."""

    level: str = Field(..., description="Risk level (low/moderate/high/extreme)")
    percentile_range: str = Field(
        ..., description="Percentile range e.g. '0-25', '25-50', etc."
    )
    min_probability: float = Field(..., description="Minimum probability for this level")
    max_probability: float = Field(..., description="Maximum probability for this level")


class DelayProbabilityResponse(BaseModel):
    """Response for deliberate delay probability scoring."""

    case_id: int = Field(..., description="ID of the case being analyzed")
    case_number: str = Field(..., description=CASE_IDENTIFIER_DESC)
    probability: float = Field(
        ...,
        description="Probability of deliberate delay (0-100)",
        ge=0,
        le=100,
    )
    percentile: float = Field(
        ...,
        description="Percentile rank against population (0-100)",
        ge=0,
        le=100,
    )
    risk_level: str = Field(
        ...,
        description="Risk classification (low/moderate/high/extreme)",
    )
    confidence: float = Field(
        ...,
        description="Confidence in the assessment (0.3-1.0)",
        ge=0.0,
        le=1.0,
    )
    primary_drivers: List[str] = Field(
        default_factory=list,
        description="Top 1-3 features driving the delay probability (anomaly sources)",
    )
    anomalies: List[str] = Field(
        default_factory=list,
        description="All detected anomalies (features with |z| > 2)",
    )
    explanation: str = Field(
        ..., description="Plain-language explanation of the assessment"
    )
    analysis_timestamp: datetime = Field(
        ..., description="When this analysis was performed"
    )
    status: str = Field(
        default="success",
        description="Status of the analysis (success or error)",
    )

    class Config:
        from_attributes = True


class CaseFeatureValues(BaseModel):
    """Feature values extracted for a case (used in batch responses)."""

    case_id: int = Field(..., description="Case ID")
    case_number: str = Field(..., description=CASE_IDENTIFIER_DESC)
    adjournment_density: float = Field(
        ..., description="Adjournment frequency normalized by case age"
    )
    party_driven_score: float = Field(
        ..., description="Score of party-driven delay tactics (0-4)"
    )
    dormancy_cv: float = Field(
        ..., description="Dormancy coefficient of variation"
    )
    bench_hunting_index: float = Field(
        ..., description="Bench hunting pattern index (0-1)"
    )


class CaseProbabilityAnalysis(BaseModel):
    """Single case analysis result for batch operations."""

    case_id: int = Field(..., description="Case ID")
    case_number: str = Field(..., description=CASE_IDENTIFIER_DESC)
    probability: float = Field(
        ...,
        description="Probability of deliberate delay (0-100)",
        ge=0,
        le=100,
    )
    risk_level: str = Field(
        ..., description="Risk classification (low/moderate/high/extreme)"
    )
    confidence: float = Field(
        ..., description="Confidence in the assessment (0.3-1.0)"
    )
    primary_drivers: List[str] = Field(
        default_factory=list, description="Top anomaly sources"
    )

    model_config = ConfigDict(from_attributes=True)


class BatchDelayAnalysisResponse(BaseModel):
    """Response for batch analysis of multiple cases."""

    analysis_type: str = Field(
        default="batch_delay_analysis",
        description="Type of analysis performed",
    )
    total_cases_analyzed: int = Field(
        ..., description="Total number of cases analyzed"
    )
    success_count: int = Field(
        ..., description="Cases with successful analysis"
    )
    error_count: int = Field(
        ..., description="Cases with errors"
    )
    results: List[CaseProbabilityAnalysis] = Field(
        ..., description="Analysis results for each case"
    )
    summary_stats: dict = Field(
        default_factory=dict,
        description="Aggregate statistics (mean, std, percentiles)",
    )
    analysis_timestamp: datetime = Field(
        ..., description="When the batch analysis was performed"
    )
    version: str = Field(
        default="1.0", description="API version for this response"
    )

    model_config = ConfigDict(from_attributes=True)


class HealthCheckResponse(BaseModel):
    """Response for delay detection system health check."""

    status: str = Field(..., description="System status (healthy/degraded/error)")
    phase1_available: bool = Field(
        ..., description="Phase 1 (tactic classification) available"
    )
    phase2_available: bool = Field(
        ..., description="Phase 2 (feature engineering) available"
    )
    phase3_available: bool = Field(
        ..., description="Phase 3 (probability scoring) available"
    )
    baseline_available: bool = Field(
        ..., description="Baseline metrics available for comparison"
    )
    baseline_sample_size: Optional[int] = Field(
        default=None, description="Sample size of current baseline"
    )
    baseline_last_updated: Optional[datetime] = Field(
        default=None, description="When baseline was last calculated"
    )
    message: Optional[str] = Field(
        default=None, description="Status message or error details"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    status: str = Field(default="error", description="Status indicator")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(
        default=None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred",
    )
