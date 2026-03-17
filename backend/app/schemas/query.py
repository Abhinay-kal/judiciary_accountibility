from datetime import date
from typing import Optional

from pydantic import BaseModel


class CaseQuery(BaseModel):
    court: Optional[str] = None
    state: Optional[str] = None
    case_type: Optional[str] = None
    party_name: Optional[str] = None
    flagged_only: bool = False
    politician_only: bool = False
    min_importance: Optional[float] = None
    min_normalized_delay: Optional[float] = None
    delay_severity: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = 1
    page_size: int = 20
