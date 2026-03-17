from pydantic import BaseModel


class CourtStatsOut(BaseModel):
    court_id: int
    court_name: str
    total_cases: int
    pending_cases: int
    disposed_cases: int
    backlog_ratio: float


class JudgeStatsOut(BaseModel):
    judge_id: int
    judge_name: str
    total_hearings: int
    adjournment_rate: float
    median_disposal_days: float
