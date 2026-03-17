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

    class Config:
        from_attributes = True


class HearingOut(BaseModel):
    id: int
    date: date
    judge_id: Optional[int]
    listing_type: Optional[str]
    outcome_text: Optional[str]
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

    class Config:
        from_attributes = True
