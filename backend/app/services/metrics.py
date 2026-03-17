from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, median, pstdev

import pandas as pd
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Adjournment, Case, Flag, Hearing


def compute_time_to_disposal(case: Case) -> int | None:
    """Compute disposal duration in days for disposed cases."""

    if case.status.lower() != "disposed" or not case.filing_date:
        return None
    last_hearing = None
    if case.hearings:
        last_hearing = max((h.date for h in case.hearings if h.date), default=None)
    if not last_hearing:
        return None
    return (last_hearing - case.filing_date).days


def compute_time_between_hearings(case: Case) -> list[int]:
    """Compute day differences between consecutive hearings."""

    hearing_dates = sorted([h.date for h in case.hearings if h.date])
    return [(hearing_dates[i] - hearing_dates[i - 1]).days for i in range(1, len(hearing_dates))]


def case_adjournment_rate(db: Session, case_id: int) -> float:
    """Adjournment rate for a case."""

    total = db.query(Hearing).filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False)).count()
    if total == 0:
        return 0.0
    adj = (
        db.query(Adjournment)
        .filter(Adjournment.case_id == case_id, Adjournment.is_adjournment.is_(True), Adjournment.is_deleted.is_(False))
        .count()
    )
    return adj / total


def judge_adjournment_rate(db: Session, judge_id: int) -> float:
    """Adjournment rate for a judge."""

    total = db.query(Hearing).filter(Hearing.judge_id == judge_id, Hearing.is_deleted.is_(False)).count()
    if total == 0:
        return 0.0
    adj = (
        db.query(Adjournment)
        .join(Hearing, Hearing.id == Adjournment.hearing_id)
        .filter(Hearing.judge_id == judge_id, Adjournment.is_adjournment.is_(True), Adjournment.is_deleted.is_(False))
        .count()
    )
    return adj / total


def judge_median_disposal_days(db: Session, judge_id: int) -> float:
    """Median disposal days for cases heard by a given judge."""

    hearings = db.query(Hearing).filter(Hearing.judge_id == judge_id, Hearing.is_deleted.is_(False)).all()
    case_ids = {h.case_id for h in hearings}
    if not case_ids:
        return 0.0

    durations = []
    cases = db.query(Case).filter(Case.id.in_(case_ids), Case.is_deleted.is_(False)).all()
    for case in cases:
        d = compute_time_to_disposal(case)
        if d is not None:
            durations.append(d)

    if not durations:
        return 0.0
    return float(median(durations))


def backlog_indicators(db: Session) -> list[dict]:
    """Compute court backlog indicators."""

    rows = (
        db.query(
            Case.court_id,
            func.count(Case.id).label("total_cases"),
            func.sum(case((Case.status == "pending", 1), else_=0)).label("pending_cases"),
            func.sum(case((Case.status == "disposed", 1), else_=0)).label("disposed_cases"),
        )
        .filter(Case.is_deleted.is_(False))
        .group_by(Case.court_id)
        .all()
    )

    results = []
    for row in rows:
        total = row.total_cases or 0
        pending = row.pending_cases or 0
        disposed = row.disposed_cases or 0
        results.append(
            {
                "court_id": row.court_id,
                "total_cases": total,
                "pending_cases": pending,
                "disposed_cases": disposed,
                "backlog_ratio": (pending / total) if total else 0.0,
            }
        )
    return results


def run_anomaly_detection(db: Session) -> int:
    """Flag anomalous cases based on hearing gaps and adjournment rates."""

    flagged = 0
    cases = db.query(Case).filter(Case.is_deleted.is_(False)).all()
    grouped_by_court: dict[int, list[Case]] = defaultdict(list)
    for case in cases:
        grouped_by_court[case.court_id].append(case)

    for court_cases in grouped_by_court.values():
        hearing_gaps = []
        adj_rates = []

        for case in court_cases:
            gaps = compute_time_between_hearings(case)
            if gaps:
                hearing_gaps.extend(gaps)
            adj_rates.append(case_adjournment_rate(db, case.id))

        if not hearing_gaps or not adj_rates:
            continue

        median_gap = median(hearing_gaps)
        avg_adj = mean(adj_rates)
        std_adj = pstdev(adj_rates) if len(adj_rates) > 1 else 0.0

        for case in court_cases:
            last_hearing_date = max((h.date for h in case.hearings if h.date), default=None)
            current_gap = (date.today() - last_hearing_date).days if last_hearing_date else 0
            case_adj_rate = case_adjournment_rate(db, case.id)
            should_flag_gap = current_gap > (2 * median_gap)
            should_flag_adj = case_adj_rate > (avg_adj + 2 * std_adj)

            if should_flag_gap or should_flag_adj:
                exists = (
                    db.query(Flag)
                    .filter(Flag.case_id == case.id, Flag.flag_type == "delay_anomaly", Flag.is_active.is_(True))
                    .first()
                )
                if exists:
                    continue
                db.add(
                    Flag(
                        case_id=case.id,
                        flag_type="delay_anomaly",
                        score=case_adj_rate,
                        details={
                            "max_hearing_gap_days": current_gap,
                            "court_median_gap_days": median_gap,
                            "case_adjournment_rate": case_adj_rate,
                            "court_adjournment_mean": avg_adj,
                            "court_adjournment_std": std_adj,
                        },
                        is_active=True,
                    )
                )
                flagged += 1

    db.commit()
    return flagged


def to_dataframe_for_export(db: Session) -> pd.DataFrame:
    """Build an analytics-friendly DataFrame from case data."""

    rows = db.query(Case).filter(Case.is_deleted.is_(False)).all()
    return pd.DataFrame(
        [
            {
                "case_uid": c.case_uid,
                "case_number": c.case_number,
                "court_id": c.court_id,
                "status": c.status,
                "filing_date": c.filing_date,
                "next_hearing_date": c.next_hearing_date,
            }
            for c in rows
        ]
    )
