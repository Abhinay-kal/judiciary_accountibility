from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
from dateutil.parser import parse as parse_date
from sqlalchemy.orm import Session

from app.models import Case


@dataclass
class SurvivalRow:
    case_id: int
    duration_days: float
    event_observed: int
    court_id: int | None
    state: str | None
    case_type: str | None
    judge_id: int | None


def _extract_disposal_date(case: Case) -> date | None:
    fields = case.source_fields or {}
    for key in (
        "disposal_date",
        "date_of_disposal",
        "decision_date",
        "date_of_decision",
        "closed_date",
        "judgement_date",
    ):
        value = fields.get(key)
        if not value:
            continue
        try:
            if isinstance(value, date):
                return value
            return parse_date(str(value)).date()
        except Exception:
            continue

    if case.status == "disposed" and case.updated_at:
        return case.updated_at.date()
    return None


def compute_duration_and_event(case: Case, *, now: date | None = None) -> tuple[float | None, int]:
    if case.filing_date is None:
        return None, 0

    today = now or date.today()
    if case.status == "disposed":
        disposal = _extract_disposal_date(case) or today
        duration = max(0.0, float((disposal - case.filing_date).days))
        return duration, 1

    return max(0.0, float((today - case.filing_date).days)), 0


def build_survival_dataset(
    db: Session,
    *,
    window_years: int | None = None,
    now: date | None = None,
) -> list[SurvivalRow]:
    today = now or date.today()

    query = db.query(Case).filter(Case.is_deleted.is_(False), Case.filing_date.is_not(None))
    if window_years is not None:
        cutoff = today - timedelta(days=max(1, window_years) * 365)
        query = query.filter(Case.filing_date >= cutoff)

    rows = query.all()
    dataset: list[SurvivalRow] = []

    for case in rows:
        duration_days, event = compute_duration_and_event(case, now=today)
        if duration_days is None:
            continue

        judge_id = None
        if case.hearings:
            latest = max(case.hearings, key=lambda hearing: hearing.date)
            judge_id = latest.judge_id

        dataset.append(
            SurvivalRow(
                case_id=case.id,
                duration_days=duration_days,
                event_observed=event,
                court_id=case.court_id,
                state=case.state,
                case_type=(case.case_type or "unknown").strip().lower() or "unknown",
                judge_id=judge_id,
            )
        )

    return dataset


def to_numpy_arrays(rows: list[SurvivalRow]) -> tuple[np.ndarray, np.ndarray]:
    durations = np.array([row.duration_days for row in rows], dtype=float)
    events = np.array([row.event_observed for row in rows], dtype=int)
    return durations, events


def sync_case_survival_fields(db: Session, *, window_years: int | None = None) -> dict[str, int]:
    rows = build_survival_dataset(db, window_years=window_years)
    by_case = {row.case_id: row for row in rows}
    updated = 0

    for case in db.query(Case).filter(Case.is_deleted.is_(False)).all():
        row = by_case.get(case.id)
        if row is None:
            continue
        case.case_duration_days = row.duration_days
        case.is_disposed = bool(row.event_observed)
        updated += 1

    db.commit()
    return {"updated": updated}
