import argparse
from datetime import date, timedelta

from app.db.session import SessionLocal
from app.ingestion.models import IngestionSource
from app.models import Adjournment, Case, CasePartyLink, Court, Hearing, Judge, Order, PublicOfficial
from app.services.adjournment import detect_adjournment


def _ensure_ingestion_sources(db) -> int:
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
    ]

    existing = {
        row[0]
        for row in db.query(IngestionSource.source_name).all()
    }
    created = 0
    for item in defaults:
        if item["source_name"] in existing:
            continue
        db.add(
            IngestionSource(
                source_name=item["source_name"],
                source_type=item["source_type"],
                base_url=item["base_url"],
                is_active=True,
                priority=item["priority"],
                expected_update_interval_minutes=item["expected_update_interval_minutes"],
                health_status="HEALTHY",
                mirror_urls=[],
                config_json={},
            )
        )
        created += 1
    return created


def run_seed(*, only_if_empty: bool = True) -> None:
    db = SessionLocal()
    try:
        created_sources = _ensure_ingestion_sources(db)

        existing_cases = db.query(Case.id).count()
        if only_if_empty and existing_cases > 0:
            db.commit()
            print(
                f"Seed skipped: cases already exist ({existing_cases}). "
                f"Ingestion sources added: {created_sources}."
            )
            return

        existing_seed_case = db.query(Case.id).filter(Case.case_uid == "seed::delhi-hc::001").first()
        if existing_seed_case:
            db.commit()
            print(
                "Seed skipped: sample case already present. "
                f"Ingestion sources added: {created_sources}."
            )
            return

        court = Court(name="Delhi High Court", level="high", state="Delhi")
        db.add(court)
        db.flush()

        judge = Judge(name="Justice A. Mehra", court_id=court.id)
        db.add(judge)
        db.flush()

        case = Case(
            case_uid="seed::delhi-hc::001",
            cnr="DLHC01000012024",
            case_number="W.P.(C) 1001/2024",
            court_id=court.id,
            court_level="high",
            state="Delhi",
            bench="Division Bench",
            judges_text="Justice A. Mehra",
            filing_date=date.today() - timedelta(days=400),
            next_hearing_date=date.today() + timedelta(days=15),
            case_type="Writ",
            status="pending",
            source_url="https://example.org/case/seed-001",
            source_fields={"status": "seed"},
        )
        db.add(case)
        db.flush()

        outcomes = [
            "Matter adjourned due to non-availability of counsel",
            "Listed for final hearing",
            "Arguments partly heard",
        ]

        for i, text in enumerate(outcomes):
            hearing = Hearing(
                case_id=case.id,
                date=(date.today() - timedelta(days=90 - i * 20)),
                judge_id=judge.id,
                listing_type="Regular",
                outcome_text=text,
                source="seed",
            )
            db.add(hearing)
            db.flush()

            is_adj, reason = detect_adjournment(text)
            db.add(
                Adjournment(
                    case_id=case.id,
                    hearing_id=hearing.id,
                    is_adjournment=is_adj,
                    reason_category=reason,
                    source="seed",
                )
            )

        db.add(Order(case_id=case.id, order_date=date.today() - timedelta(days=5), order_link="https://example.org/order.pdf", source="seed"))

        official = PublicOfficial(full_name="Shri Example Minister", role="Minister", source="seed")
        db.add(official)
        db.flush()

        db.add(
            CasePartyLink(
                case_id=case.id,
                party_type="petitioner",
                party_name="Shri Example Minister",
                official_id=official.id,
                match_confidence=0.99,
                is_verified=True,
            )
        )

        db.commit()
        print(f"Seed completed. Ingestion sources added: {created_sources}. Sample data loaded.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load sample data for local development.")
    parser.add_argument(
        "--always",
        action="store_true",
        help="Attempt to seed even when existing rows are present.",
    )
    args = parser.parse_args()
    run_seed(only_if_empty=not args.always)
