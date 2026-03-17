from datetime import date, timedelta

from app.db.session import SessionLocal
from app.models import Adjournment, Case, CasePartyLink, Court, Hearing, Judge, Order, PublicOfficial
from app.services.adjournment import detect_adjournment


def run_seed() -> None:
    db = SessionLocal()
    try:
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
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
