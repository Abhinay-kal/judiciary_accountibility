from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.orm import Query

from app.models import Case, Court


class ExportFilters(BaseModel):
    state: str | None = None
    court: str | None = None
    case_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None
    min_importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_rows: int = Field(default=100_000, ge=1, le=500_000)


@dataclass(slots=True)
class PaginationWindow:
    offset: int = 0
    limit: int = 10_000


def apply_case_export_filters(query: Query, filters: ExportFilters) -> Query:
    query = query.filter(Case.is_deleted.is_(False))

    if filters.state:
        query = query.filter(Case.state == filters.state)
    if filters.case_type:
        query = query.filter(Case.case_type == filters.case_type)
    if filters.status:
        query = query.filter(Case.status == filters.status)
    if filters.min_importance_score is not None:
        query = query.filter(Case.importance_score.is_not(None), Case.importance_score >= filters.min_importance_score)
    if filters.date_from:
        query = query.filter(Case.filing_date.is_not(None), Case.filing_date >= filters.date_from)
    if filters.date_to:
        query = query.filter(Case.filing_date.is_not(None), Case.filing_date <= filters.date_to)
    if filters.court:
        query = query.join(Court, Case.court_id == Court.id).filter(Court.name == filters.court)

    return query


def apply_dict_filters(rows: list[dict], filters: ExportFilters) -> list[dict]:
    output = rows
    if filters.state:
        output = [row for row in output if row.get("state") == filters.state]
    if filters.case_type:
        output = [row for row in output if row.get("case_type") == filters.case_type]
    if filters.status:
        output = [row for row in output if row.get("status") == filters.status]
    if filters.min_importance_score is not None:
        output = [
            row
            for row in output
            if row.get("importance_score") is not None and float(row.get("importance_score", 0.0)) >= filters.min_importance_score
        ]
    return output
