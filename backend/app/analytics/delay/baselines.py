from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
from dateutil.parser import parse as parse_date
from sqlalchemy.orm import Session

from app.analytics.delay.trends import time_weighted_median
from app.models import Case, DelayBaseline

BASELINE_COURT_CASE_TYPE = "court_case_type"
BASELINE_COURT = "court"
BASELINE_STATE_CASE_TYPE = "state_case_type"
BASELINE_STATE = "state"
BASELINE_NATIONAL_CASE_TYPE = "national_case_type"
BASELINE_NATIONAL = "national"


@dataclass
class BaselineStats:
    median_delay: float
    p75_delay: float
    p90_delay: float
    iqr_delay: float
    sample_size: int


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
        raw = fields.get(key)
        if not raw:
            continue
        try:
            if isinstance(raw, date):
                return raw
            return parse_date(str(raw)).date()
        except Exception:
            continue

    if case.status == "disposed" and case.updated_at:
        return case.updated_at.date()
    return None


def compute_case_delay_days(case: Case, *, now: date | None = None) -> float | None:
    if case.filing_date is None:
        return None

    ref_now = now or date.today()
    if case.status == "disposed":
        disposal = _extract_disposal_date(case)
        if disposal is None:
            disposal = case.updated_at.date() if case.updated_at else ref_now
        return max(0.0, float((disposal - case.filing_date).days))

    return max(0.0, float((ref_now - case.filing_date).days))


def _stats(delays: list[float], *, use_time_weighted: bool, timestamps: list[datetime], half_life_days: int) -> BaselineStats:
    arr = np.array([float(value) for value in delays], dtype=float)
    if len(arr) == 0:
        return BaselineStats(0.0, 0.0, 0.0, 0.0, 0)

    if use_time_weighted:
        median_delay = time_weighted_median(delays, timestamps, half_life_days=half_life_days)
    else:
        median_delay = float(np.median(arr))
    p75 = float(np.percentile(arr, 75))
    p90 = float(np.percentile(arr, 90))
    p25 = float(np.percentile(arr, 25))
    iqr = max(1.0, p75 - p25)
    return BaselineStats(
        median_delay=max(1.0, round(median_delay, 4)),
        p75_delay=max(1.0, round(p75, 4)),
        p90_delay=max(1.0, round(p90, 4)),
        iqr_delay=round(iqr, 4),
        sample_size=int(len(arr)),
    )


def build_and_store_delay_baselines(
    db: Session,
    *,
    window_years: int = 7,
    use_time_weighted: bool = False,
    half_life_days: int = 730,
) -> dict[str, int]:
    today = date.today()
    cutoff = today - timedelta(days=max(1, window_years) * 365)

    rows = (
        db.query(Case)
        .filter(Case.is_deleted.is_(False), Case.filing_date.is_not(None), Case.filing_date >= cutoff)
        .all()
    )

    groups: dict[tuple[str, int | None, str | None, str | None], list[tuple[float, datetime]]] = defaultdict(list)

    used_rows = 0
    for case in rows:
        if case.filing_date is None or case.filing_date < cutoff:
            continue
        used_rows += 1
        delay = compute_case_delay_days(case, now=today)
        if delay is None:
            continue

        ts = case.last_source_updated_at or case.updated_at
        if ts is None:
            ts = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        normalized_case_type = (case.case_type or "unknown").strip().lower() or "unknown"

        groups[(BASELINE_COURT_CASE_TYPE, case.court_id, None, normalized_case_type)].append((delay, ts))
        groups[(BASELINE_COURT, case.court_id, None, None)].append((delay, ts))
        groups[(BASELINE_STATE_CASE_TYPE, None, case.state, normalized_case_type)].append((delay, ts))
        groups[(BASELINE_STATE, None, case.state, None)].append((delay, ts))
        groups[(BASELINE_NATIONAL_CASE_TYPE, None, None, normalized_case_type)].append((delay, ts))
        groups[(BASELINE_NATIONAL, None, None, None)].append((delay, ts))

    db.query(DelayBaseline).delete()
    inserted = 0

    for (level, court_id, state, case_type), payload in groups.items():
        delays = [item[0] for item in payload]
        timestamps = [item[1] for item in payload]
        stats = _stats(delays, use_time_weighted=use_time_weighted, timestamps=timestamps, half_life_days=half_life_days)
        if stats.sample_size <= 0:
            continue

        db.add(
            DelayBaseline(
                court_id=court_id,
                state=state,
                case_type=case_type,
                baseline_level=level,
                median_delay=stats.median_delay,
                p75_delay=stats.p75_delay,
                p90_delay=stats.p90_delay,
                iqr_delay=stats.iqr_delay,
                sample_size=stats.sample_size,
                window_years=window_years,
            )
        )
        inserted += 1

    db.commit()
    return {"cases_considered": used_rows, "baselines_written": inserted}
