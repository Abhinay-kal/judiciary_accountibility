from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models import CasePartyLink, PublicOfficial


def import_public_officials_from_csv(db: Session, csv_path: str) -> int:
    """Import public officials from a CSV file with full_name, role, source columns."""

    imported = 0
    with Path(csv_path).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                continue
            exists = db.query(PublicOfficial).filter(PublicOfficial.full_name == full_name).first()
            if exists:
                continue
            db.add(PublicOfficial(full_name=full_name, role=row.get("role"), source=row.get("source")))
            imported += 1
    db.commit()
    return imported


def fuzzy_tag_case_parties(db: Session, threshold: int = 85) -> int:
    """Fuzzy match case parties against public officials and create potential links."""

    officials = db.query(PublicOfficial).filter(PublicOfficial.is_deleted.is_(False)).all()
    party_links = db.query(CasePartyLink).filter(CasePartyLink.is_deleted.is_(False)).all()

    updates = 0
    for party_link in party_links:
        best_score = 0
        best_official = None
        for official in officials:
            score = fuzz.token_set_ratio(party_link.party_name, official.full_name)
            if score > best_score:
                best_score = score
                best_official = official

        if best_official and best_score >= threshold:
            party_link.official_id = best_official.id
            party_link.match_confidence = round(best_score / 100.0, 2)
            updates += 1

    db.commit()
    return updates
