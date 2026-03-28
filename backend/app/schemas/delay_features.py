"""
Pydantic schemas for Phase 2 Delay Feature Engineering.

Defines data structures for adjournment density, party-driven delay scoring,
dormancy variance analysis, and bench hunting index detection.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DelayScoreLevel(str, Enum):
    """Categorical levels for delay scores."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class BenchHuntingLevel(str, Enum):
    """Levels for bench hunting/forum shopping."""
    NO_HUNTING = "NO_HUNTING"
    MINIMAL = "MINIMAL"
    MODERATE = "MODERATE"
    SIGNIFICANT = "SIGNIFICANT"
    EXTENSIVE = "EXTENSIVE"


class AdjournmentDensityMetrics(BaseModel):
    """Metrics for adjournment density (Phase 2.1)."""
    
    case_id: int = Field(..., description="Case ID")
    total_hearings: int = Field(..., ge=0, description="Total number of hearings")
    total_adjournments: int = Field(..., ge=0, description="Number of adjournments")
    density_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of hearings that were adjourned")
    population_mean: float = Field(..., ge=0.0, description="Population mean adjournment density")
    population_std_dev: float = Field(..., ge=0.0, description="Population standard deviation")
    z_score: float = Field(..., description="Z-score deviation from population mean")
    is_outlier: bool = Field(..., description="True if density > mean + 2*std_dev")
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator("density_percentage", mode="before")
    @classmethod
    def validate_density(cls, v: float) -> float:
        """Ensure density is between 0 and 100."""
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"Density must be 0-100, got {v}")
        return round(v, 2)


class PartyDrivenDelayMetrics(BaseModel):
    """Metrics for party-driven delay scoring (Phase 2.2)."""
    
    model_config = ConfigDict(use_enum_values=False)
    
    case_id: int = Field(..., description="Case ID")
    total_adjournments: int = Field(..., ge=0, description="Total adjournments in case")
    party_requested_adjournments: int = Field(..., ge=0, description="Adjournments requested by party/counsel")
    court_requested_adjournments: int = Field(..., ge=0, description="Adjournments initiated by court")
    party_request_percentage: float = Field(..., ge=0.0, le=100.0, description="% of adjournments requested by party")
    level: DelayScoreLevel = Field(..., description="Categorical level (LOW, MODERATE, HIGH, EXTREME)")
    contributing_advocates: dict[int, int] = Field(
        default_factory=dict,
        description="Advocate ID -> adjournment count mapping"
    )
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class DormancyVarianceMetrics(BaseModel):
    """Metrics for dormancy variance analysis (Phase 2.3)."""
    
    case_id: int = Field(..., description="Case ID")
    hearing_gaps_days: list[int] = Field(
        default_factory=list,
        description="List of gap lengths (in days) between consecutive hearings"
    )
    min_gap_days: int = Field(..., ge=0, description="Minimum gap between hearings")
    max_gap_days: int = Field(..., ge=0, description="Maximum gap between hearings")
    mean_gap_days: float = Field(..., ge=0.0, description="Mean gap between hearings")
    variance: float = Field(..., ge=0.0, description="Variance of gap lengths")
    std_dev_days: float = Field(..., ge=0.0, description="Standard deviation of gaps")
    coefficient_of_variation: float = Field(..., ge=0.0, description="Std dev / mean (measure of irregularity)")
    is_irregular_pattern: bool = Field(
        ...,
        description="True if coefficient_of_variation > population median, indicating deliberate sporadic delays"
    )
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class BenchHuntingMetrics(BaseModel):
    """Metrics for bench hunting/forum shopping (Phase 2.4)."""
    
    model_config = ConfigDict(use_enum_values=False)
    
    case_id: int = Field(..., description="Case ID")
    primary_court_id: int = Field(..., description="Primary court for this case")
    unique_courts_used: set[int] = Field(
        default_factory=set,
        description="Set of distinct court IDs used in related matters"
    )
    unique_courts_count: int = Field(..., ge=1, description="Number of distinct courts used")
    bench_changes: int = Field(..., ge=0, description="Number of bench changes in same court")
    hunting_index: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Composite score 0-10, higher = more forum shopping"
    )
    level: BenchHuntingLevel = Field(..., description="Categorical level of bench hunting")
    indicators: list[str] = Field(
        default_factory=list,
        description="List of specific indicators (e.g., 'multiple_courts', 'frequent_bench_changes')"
    )
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class CaseDelayFeatures(BaseModel):
    """Complete delay feature set for a case (Phase 2 output)."""
    
    model_config = ConfigDict(use_enum_values=False)
    
    case_id: int = Field(..., description="Case ID")
    adjournment_density: AdjournmentDensityMetrics = Field(..., description="Adjournment density metrics")
    party_driven_delay: PartyDrivenDelayMetrics = Field(..., description="Party-driven delay metrics")
    dormancy_variance: DormancyVarianceMetrics = Field(..., description="Dormancy variance metrics")
    bench_hunting: BenchHuntingMetrics = Field(..., description="Bench hunting metrics")
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class FeatureExtractionResult(BaseModel):
    """Result of batch feature extraction."""
    
    total_cases: int = Field(..., description="Total cases processed")
    successful: int = Field(..., description="Cases successfully processed")
    failed: int = Field(..., description="Cases that failed")
    error_cases: list[dict] = Field(
        default_factory=list,
        description="List of {case_id, error_message} for failed cases"
    )
    processing_time_seconds: float = Field(..., ge=0.0, description="Total processing time")
    features: list[CaseDelayFeatures] = Field(
        default_factory=list,
        description="Extracted features for successful cases"
    )
