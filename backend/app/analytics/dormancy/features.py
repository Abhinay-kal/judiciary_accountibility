from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Adjournment, Case, Hearing, Order


_SUBSTANTIVE_OUTCOME_TYPES = {"HEARD", "DISPOSED", "ORDER_RESERVED"}


@dataclass
class DormancyFeatures:
    case_id: int
    status: str
    is_disposed: bool
    state: str | None
    case_type: str | None
    case_stage: str | None
    court_id: int
    days_since_last_hearing: int | None
    days_since_last_order: int | None
    days_since_last_listing: int | None
    case_age_days: int | None
    number_of_hearings: int
    adjournment_count: int
    bail_status: str | None
    stay_status: str | None
    future_listing_exists: bool
    days_since_last_activity: int | None
    last_activity_date: date | None
    trend_worsening: bool
    recent_transfer: bool
    data_confidence: float


def _norm_status(value: str | None) -> str:
    return (value or "").strip().lower()


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _days_since(ref: date | None, today: date) -> int | None:
    if ref is None:
        return None
    return max(0, (today - ref).days)


def _future_listing_exists(case: Case, *, today: date, upcoming_days: int = 30) -> bool:
    if case.next_hearing_date is None:
        return False
    return case.next_hearing_date >= today and (case.next_hearing_date - today).days <= upcoming_days


def _is_recent_transfer(source_fields: dict[str, Any], *, today: date, transfer_grace_days: int = 90) -> bool:
    transfer_keys = ("transferred_on", "transfer_date", "date_of_transfer", "court_transfer_date")
    transfer_dt: date | None = None
    for key in transfer_keys:
        transfer_dt = _as_date(source_fields.get(key))
        if transfer_dt is not None:
            break
    if transfer_dt is None:
        return False
    return (today - transfer_dt).days <= transfer_grace_days


def _trend_worsening(hearing_dates: list[date]) -> bool:
    if len(hearing_dates) < 4:
        return False
    hearing_dates = sorted(hearing_dates)
    gaps = [(hearing_dates[idx] - hearing_dates[idx - 1]).days for idx in range(1, len(hearing_dates))]
    if len(gaps) < 3:
        return False
    recent = gaps[-3:]
    return recent[0] < recent[1] < recent[2]


def extract_case_features(db: Session, case: Case, *, today: date | None = None, future_listing_horizon_days: int = 30) -> DormancyFeatures:
    ref_today = today or date.today()
    source_fields = case.source_fields or {}

    hearings = (
        db.query(Hearing)
        .filter(Hearing.case_id == case.id, Hearing.is_deleted.is_(False))
        .order_by(Hearing.date.asc())
        .all()
    )
    orders = (
        db.query(Order)
        .filter(Order.case_id == case.id, Order.is_deleted.is_(False), Order.order_date.is_not(None))
        .order_by(Order.order_date.asc())
        .all()
    )

    substantive_hearing_dates = [
        hearing.date
        for hearing in hearings
        if ((hearing.outcome_type.value if hearing.outcome_type else "").upper() in _SUBSTANTIVE_OUTCOME_TYPES)
    ]
    listing_dates = [hearing.date for hearing in hearings]
    order_dates = [order.order_date for order in orders if order.order_date is not None]

    last_substantive = max(substantive_hearing_dates) if substantive_hearing_dates else None
    last_listing = max(listing_dates) if listing_dates else None
    last_order = max(order_dates) if order_dates else None
    filing_date = case.filing_date

    last_activity_date = max([dt for dt in (last_substantive, last_order, last_listing) if dt is not None], default=None)

    adjournment_count = (
        db.query(Adjournment)
        .filter(Adjournment.case_id == case.id, Adjournment.is_deleted.is_(False), Adjournment.is_adjournment.is_(True))
        .count()
    )

    available_points = [
        case.filing_date is not None,
        len(listing_dates) > 0,
        len(order_dates) > 0,
        case.status is not None,
    ]
    data_confidence = sum(1 for ok in available_points if ok) / float(len(available_points))

    stage = source_fields.get("case_stage") or source_fields.get("stage")
    bail_status = source_fields.get("bail_status")
    stay_status = source_fields.get("stay_status")

    return DormancyFeatures(
        case_id=case.id,
        status=case.status,
        is_disposed=bool(case.is_disposed) or _norm_status(case.status) == "disposed",
        state=case.state,
        case_type=case.case_type,
        case_stage=str(stage).strip().lower() if stage else None,
        court_id=case.court_id,
        days_since_last_hearing=_days_since(last_substantive, ref_today),
        days_since_last_order=_days_since(last_order, ref_today),
        days_since_last_listing=_days_since(last_listing, ref_today),
        case_age_days=_days_since(filing_date, ref_today),
        number_of_hearings=len(listing_dates),
        adjournment_count=adjournment_count,
        bail_status=str(bail_status).strip().lower() if bail_status else None,
        stay_status=str(stay_status).strip().lower() if stay_status else None,
        future_listing_exists=_future_listing_exists(case, today=ref_today, upcoming_days=future_listing_horizon_days),
        days_since_last_activity=_days_since(last_activity_date, ref_today),
        last_activity_date=last_activity_date,
        trend_worsening=_trend_worsening(listing_dates),
        recent_transfer=_is_recent_transfer(source_fields, today=ref_today),
        data_confidence=round(data_confidence, 3),
    )
