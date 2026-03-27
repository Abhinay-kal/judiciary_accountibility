from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Iterator, TypeVar

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ingestion.models import IngestionSource
from app.models import Adjournment, Case, CasePartyLink, Court, Hearing, Judge, Order, PublicOfficial
from app.services.adjournment import detect_adjournment

T = TypeVar("T")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around seed operations."""

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_or_create(
    db: Session,
    model: type[T],
    *,
    lookup: dict,
    defaults: dict | None = None,
) -> tuple[T, bool]:
    """Get an existing row by lookup fields or create one."""

    instance = db.query(model).filter_by(**lookup).one_or_none()
    if instance is not None:
        return instance, False
    payload = {**lookup, **(defaults or {})}
    instance = model(**payload)
    db.add(instance)
    db.flush()
    return instance, True


def update_instance(instance: object, values: dict) -> None:
    for key, value in values.items():
        setattr(instance, key, value)


def _soft_delete_rows(rows: list[object]) -> None:
    timestamp = datetime.now(timezone.utc)
    for row in rows:
        setattr(row, "is_deleted", True)
        setattr(row, "deleted_at", timestamp)


def _dedupe_seed_entities(db: Session, *, case_id: int, hearing_dates: list[date], order_date: date) -> None:
    hearing_date_set = set(hearing_dates)

    # Remove extra active seed hearings outside canonical schedule.
    extra_hearings = (
        db.query(Hearing)
        .filter(
            Hearing.case_id == case_id,
            Hearing.source == "seed",
            Hearing.is_deleted.is_(False),
        )
        .all()
    )
    _soft_delete_rows([row for row in extra_hearings if row.date not in hearing_date_set])

    # Keep one active hearing per (case_id, date)
    for hearing_date in hearing_dates:
        hearings = (
            db.query(Hearing)
            .filter(Hearing.case_id == case_id, Hearing.date == hearing_date)
            .order_by(Hearing.id.asc())
            .all()
        )
        active = [row for row in hearings if not row.is_deleted]
        if len(active) > 1:
            _soft_delete_rows(active[1:])

    # Keep one active adjournment per hearing
    hearing_ids = [
        row.id
        for row in db.query(Hearing)
        .filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False))
        .all()
    ]
    for hearing_id in hearing_ids:
        rows = (
            db.query(Adjournment)
            .filter(Adjournment.hearing_id == hearing_id)
            .order_by(Adjournment.id.asc())
            .all()
        )
        active = [row for row in rows if not row.is_deleted]
        if len(active) > 1:
            _soft_delete_rows(active[1:])

    # Remove active adjournments no longer tied to canonical active hearings.
    stale_adjournments = (
        db.query(Adjournment)
        .filter(
            Adjournment.case_id == case_id,
            Adjournment.is_deleted.is_(False),
            Adjournment.hearing_id.isnot(None),
            Adjournment.hearing_id.notin_(hearing_ids),
        )
        .all()
    )
    _soft_delete_rows(stale_adjournments)

    # Keep one active seed order for the canonical seed order key
    orders = (
        db.query(Order)
        .filter(
            Order.case_id == case_id,
            Order.order_date == order_date,
            Order.order_link == "https://example.org/order.pdf",
        )
        .order_by(Order.id.asc())
        .all()
    )
    active_orders = [row for row in orders if not row.is_deleted]
    if len(active_orders) > 1:
        _soft_delete_rows(active_orders[1:])

    extra_orders = (
        db.query(Order)
        .filter(
            Order.case_id == case_id,
            Order.source == "seed",
            Order.is_deleted.is_(False),
            (
                (Order.order_date != order_date)
                | (Order.order_link != "https://example.org/order.pdf")
            ),
        )
        .all()
    )
    _soft_delete_rows(extra_orders)

    # Keep one active official and party link for seed identity
    officials = (
        db.query(PublicOfficial)
        .filter(PublicOfficial.full_name == "Shri Example Minister", PublicOfficial.role == "Minister")
        .order_by(PublicOfficial.id.asc())
        .all()
    )
    active_officials = [row for row in officials if not row.is_deleted]
    if len(active_officials) > 1:
        _soft_delete_rows(active_officials[1:])

    links = (
        db.query(CasePartyLink)
        .filter(
            CasePartyLink.case_id == case_id,
            CasePartyLink.party_type == "petitioner",
            CasePartyLink.party_name == "Shri Example Minister",
        )
        .order_by(CasePartyLink.id.asc())
        .all()
    )
    active_links = [row for row in links if not row.is_deleted]
    if len(active_links) > 1:
        _soft_delete_rows(active_links[1:])


def _ensure_ingestion_sources(db: Session) -> int:
    defaults = [
        {
            "source_name": "njdg",
            "source_type": "API",
            "base_url": "https://njdg.ecourts.gov.in/",
            "priority": 1,
            "expected_update_interval_minutes": 1440,
        },
        {
            "source_name": "ecourts_services",
            "source_type": "SCRAPER",
            "base_url": "https://services.ecourts.gov.in/",
            "priority": 2,
            "expected_update_interval_minutes": 720,
        },
        {
            "source_name": "supreme_court_causelist",
            "source_type": "HTML",
            "base_url": "https://main.sci.gov.in/",
            "priority": 2,
            "expected_update_interval_minutes": 1440,
        },
        {
            "source_name": "high_court",
            "source_type": "HTML",
            "base_url": "https://www.allahabadhighcourt.in/",
            "priority": 3,
            "expected_update_interval_minutes": 1440,
        },
    ]

    created = 0
    for item in defaults:
        source, was_created = get_or_create(
            db,
            IngestionSource,
            lookup={"source_name": item["source_name"]},
            defaults={
                "source_type": item["source_type"],
                "base_url": item["base_url"],
                "is_active": True,
                "priority": item["priority"],
                "expected_update_interval_minutes": item["expected_update_interval_minutes"],
                "health_status": "HEALTHY",
                "mirror_urls": [],
                "config_json": {},
            },
        )
        update_instance(
            source,
            {
                "source_type": item["source_type"],
                "base_url": item["base_url"],
                "is_active": True,
                "priority": item["priority"],
                "expected_update_interval_minutes": item["expected_update_interval_minutes"],
                "health_status": "HEALTHY",
                "mirror_urls": source.mirror_urls or [],
                "config_json": source.config_json or {},
            },
        )
        if was_created:
            created += 1

    return created


def _upsert_seed_graph(db: Session) -> None:
    seed_uid = "seed::delhi-hc::001"
    filing_date = date(2024, 2, 1)
    next_hearing_date = date(2026, 4, 15)
    hearing_dates = [
        date(2026, 1, 10),
        date(2026, 2, 5),
        date(2026, 3, 1),
    ]
    order_date = date(2026, 3, 20)

    court, _ = get_or_create(
        db,
        Court,
        lookup={"name": "Delhi High Court"},
        defaults={"level": "high", "state": "Delhi", "is_deleted": False},
    )
    update_instance(court, {"level": "high", "state": "Delhi", "is_deleted": False, "deleted_at": None})
    db.flush()

    judge, _ = get_or_create(
        db,
        Judge,
        lookup={"name": "Justice A. Mehra", "court_id": court.id},
        defaults={"is_deleted": False},
    )
    update_instance(judge, {"court_id": court.id, "is_deleted": False, "deleted_at": None})
    db.flush()

    case_defaults = {
        "cnr": "DLHC01000012024",
        "case_number": "W.P.(C) 1001/2024",
        "court_id": court.id,
        "court_level": "high",
        "state": "Delhi",
        "bench": "Division Bench",
        "judges_text": "Justice A. Mehra",
        "filing_date": filing_date,
        "next_hearing_date": next_hearing_date,
        "case_type": "Writ",
        "status": "pending",
        "source_url": "https://example.org/case/seed-001",
        "source_fields": {"status": "seed"},
        "is_deleted": False,
    }
    case, _ = get_or_create(db, Case, lookup={"case_uid": seed_uid}, defaults=case_defaults)
    update_instance(case, case_defaults | {"deleted_at": None})
    db.flush()

    outcomes = [
        "Matter adjourned due to non-availability of counsel",
        "Listed for final hearing",
        "Arguments partly heard",
    ]
    for i, text in enumerate(outcomes):
        hearing_date = hearing_dates[i]
        hearing, _ = get_or_create(
            db,
            Hearing,
            lookup={
                "case_id": case.id,
                "date": hearing_date,
            },
            defaults={
                "judge_id": judge.id,
                "listing_type": "Regular",
                "outcome_text": text,
                "raw_outcome_text": text,
                "source": "seed",
                "is_deleted": False,
            },
        )
        update_instance(
            hearing,
            {
                "judge_id": judge.id,
                "listing_type": "Regular",
                "outcome_text": text,
                "raw_outcome_text": text,
                "source": "seed",
                "is_deleted": False,
                "deleted_at": None,
            },
        )
        db.flush()

        is_adj, reason = detect_adjournment(text)
        adjournment, _ = get_or_create(
            db,
            Adjournment,
            lookup={"hearing_id": hearing.id},
            defaults={
                "case_id": case.id,
                "is_adjournment": is_adj,
                "reason_category": reason,
                "source": "seed",
                "is_deleted": False,
            },
        )
        update_instance(
            adjournment,
            {
                "case_id": case.id,
                "is_adjournment": is_adj,
                "reason_category": reason,
                "source": "seed",
                "is_deleted": False,
                "deleted_at": None,
            },
        )

    order, _ = get_or_create(
        db,
        Order,
        lookup={"case_id": case.id, "order_date": order_date, "order_link": "https://example.org/order.pdf"},
        defaults={"source": "seed", "is_deleted": False},
    )
    update_instance(order, {"source": "seed", "is_deleted": False, "deleted_at": None})

    official, _ = get_or_create(
        db,
        PublicOfficial,
        lookup={"full_name": "Shri Example Minister", "role": "Minister"},
        defaults={"source": "seed", "is_deleted": False},
    )
    update_instance(official, {"source": "seed", "is_deleted": False, "deleted_at": None})
    db.flush()

    party_link, _ = get_or_create(
        db,
        CasePartyLink,
        lookup={
            "case_id": case.id,
            "party_type": "petitioner",
            "party_name": "Shri Example Minister",
        },
        defaults={
            "official_id": official.id,
            "match_confidence": 0.99,
            "is_verified": True,
            "is_deleted": False,
        },
    )
    update_instance(
        party_link,
        {
            "official_id": official.id,
            "match_confidence": 0.99,
            "is_verified": True,
            "is_deleted": False,
            "deleted_at": None,
        },
    )

    _dedupe_seed_entities(db, case_id=case.id, hearing_dates=hearing_dates, order_date=order_date)


def run_seed(*, only_if_empty: bool = True) -> None:
    with session_scope() as db:
        created_sources = _ensure_ingestion_sources(db)

        existing_cases = db.query(Case.id).count()
        if only_if_empty and existing_cases > 0:
            print(
                f"Seed skipped: cases already exist ({existing_cases}). "
                f"Ingestion sources added: {created_sources}."
            )
            return

        _upsert_seed_graph(db)
        print(f"Seed completed idempotently. Ingestion sources added: {created_sources}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load sample data for local development.")
    parser.add_argument(
        "--always",
        action="store_true",
        help="Attempt to seed even when existing rows are present.",
    )
    args = parser.parse_args()
    run_seed(only_if_empty=not args.always)
