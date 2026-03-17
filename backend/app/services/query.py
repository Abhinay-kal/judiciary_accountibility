from __future__ import annotations

from sqlalchemy.orm import Query

from app.models import Case, CasePartyLink, Court, Flag
from app.schemas.query import CaseQuery


def apply_case_filters(query: Query, filters: CaseQuery) -> Query:
    """Apply filter options for case listing queries."""

    if filters.court:
        query = query.join(Court, Court.id == Case.court_id).filter(Court.name.ilike(f"%{filters.court}%"))
    if filters.state:
        query = query.filter(Case.state.ilike(f"%{filters.state}%"))
    if filters.case_type:
        query = query.filter(Case.case_type.ilike(f"%{filters.case_type}%"))
    if filters.party_name:
        query = query.join(CasePartyLink, CasePartyLink.case_id == Case.id).filter(
            CasePartyLink.party_name.ilike(f"%{filters.party_name}%")
        )
    if filters.start_date:
        query = query.filter(Case.filing_date >= filters.start_date)
    if filters.end_date:
        query = query.filter(Case.filing_date <= filters.end_date)
    if filters.min_importance is not None:
        query = query.filter(Case.importance_score.is_not(None), Case.importance_score >= filters.min_importance)
    if filters.min_normalized_delay is not None:
        query = query.filter(Case.normalized_delay.is_not(None), Case.normalized_delay >= filters.min_normalized_delay)
    if filters.delay_severity:
        query = query.filter(Case.delay_severity == filters.delay_severity)
    if filters.flagged_only:
        query = query.join(Flag, Flag.case_id == Case.id).filter(Flag.is_active.is_(True))
    if filters.politician_only:
        query = query.join(CasePartyLink, CasePartyLink.case_id == Case.id).filter(CasePartyLink.official_id.is_not(None))
    return query


def paginate(query: Query, page: int, page_size: int):
    """Apply offset-limit pagination."""

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total
