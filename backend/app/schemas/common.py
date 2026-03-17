from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class DateRangeFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CourtOut(BaseModel):
    id: int
    name: str
    level: str
    state: str

    class Config:
        from_attributes = True


class JudgeOut(BaseModel):
    id: int
    name: str
    court_id: Optional[int]

    class Config:
        from_attributes = True


class CaseOut(BaseModel):
    id: int
    case_uid: str
    cnr: Optional[str]
    case_number: str
    court_id: int
    state: str
    filing_date: Optional[date]
    next_hearing_date: Optional[date]
    case_type: Optional[str]
    status: str
    source_url: str
    last_source_updated_at: Optional[datetime]
    importance_score: Optional[float] = None
    importance_confidence: Optional[float] = None
    importance_components: Optional[dict] = None
    last_scored_at: Optional[datetime] = None
    importance_explanation: Optional[str] = None
    importance_provenance: Optional[dict] = None
    normalized_delay: Optional[float] = None
    delay_percentile: Optional[float] = None
    robust_z_score: Optional[float] = None
    delay_severity: Optional[str] = None
    baseline_level_used: Optional[str] = None
    baseline_sample_size: Optional[int] = None
    baseline_confidence: Optional[float] = None
    last_baseline_update: Optional[datetime] = None
    plain_summary_short: Optional[str] = None
    plain_summary_detailed: Optional[str] = None
    summary_confidence: Optional[float] = None
    last_summary_update: Optional[datetime] = None
    plain_summary: Optional[dict] = None
    impact_headline: Optional[str] = None
    impact_summary: Optional[str] = None
    impact_confidence: Optional[float] = None
    impact_last_updated: Optional[datetime] = None
    dormancy_status: Optional[str] = None
    dormancy_score: Optional[float] = None
    days_since_last_activity: Optional[int] = None
    last_activity_date: Optional[date] = None
    dormancy_last_updated: Optional[datetime] = None
    impact_content: Optional[dict] = None
    delay_summary: Optional[str] = None
    public_status: Optional[str] = None
    public_note: Optional[str] = None
    last_label_at: Optional[datetime] = None
    last_label_id: Optional[int] = None

    class Config:
        from_attributes = True


class HearingOut(BaseModel):
    id: int
    date: date
    judge_id: Optional[int]
    listing_type: Optional[str]
    raw_bench: Optional[str]
    outcome_text: Optional[str]
    outcome_type: Optional[str]
    outcome_confidence: Optional[float]
    raw_outcome_text: Optional[str]
    parser_version: Optional[str]
    annotated_by: Optional[int]
    annotated_at: Optional[datetime]
    needs_verification: bool = False
    evidence_bundle: Optional[dict] = None
    judge_assignments: Optional[list[dict]] = None
    source: str

    class Config:
        from_attributes = True


class FlagOut(BaseModel):
    id: int
    case_id: int
    flag_type: str
    score: Optional[float]
    details: dict
    is_active: bool
    public_status: Optional[str] = None
    public_note: Optional[str] = None
    last_label_at: Optional[datetime] = None
    last_label_id: Optional[int] = None

    class Config:
        from_attributes = True
