from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.investigation.versioning import compute_content_hash, next_version_number
from app.models import InvestigationSnapshot

logger = logging.getLogger(__name__)


class SnapshotService:
    def __init__(self, db: Session):
        self.db = db

    def get_current(self, case_id: int) -> InvestigationSnapshot | None:
        return (
            self.db.query(InvestigationSnapshot)
            .filter(InvestigationSnapshot.case_id == case_id, InvestigationSnapshot.is_current.is_(True))
            .one_or_none()
        )

    def get_version(self, case_id: int, version_number: int) -> InvestigationSnapshot | None:
        return (
            self.db.query(InvestigationSnapshot)
            .filter(
                InvestigationSnapshot.case_id == case_id,
                InvestigationSnapshot.version_number == version_number,
            )
            .one_or_none()
        )

    def list_versions(self, case_id: int) -> list[dict[str, Any]]:
        rows = (
            self.db.query(InvestigationSnapshot)
            .filter(InvestigationSnapshot.case_id == case_id)
            .order_by(InvestigationSnapshot.version_number.desc())
            .all()
        )
        return [
            {
                "snapshot_id": row.snapshot_id,
                "version_number": row.version_number,
                "content_hash": row.content_hash,
                "generated_at": row.generated_at,
                "data_cutoff_date": row.data_cutoff_date,
                "is_current": row.is_current,
            }
            for row in rows
        ]

    def create_snapshot_if_changed(
        self,
        *,
        case_id: int,
        report: dict[str, Any],
        data_cutoff_date: date | None,
    ) -> InvestigationSnapshot:
        report_hash = compute_content_hash(report)
        current = self.get_current(case_id)

        if current is not None and current.content_hash == report_hash:
            logger.info(
                "Investigation snapshot unchanged case_id=%s version=%s hash=%s",
                case_id,
                current.version_number,
                report_hash,
            )
            return current

        next_version = next_version_number(current.version_number if current else None)
        if current is not None:
            current.is_current = False

        row = InvestigationSnapshot(
            case_id=case_id,
            version_number=next_version,
            content_hash=report_hash,
            data_cutoff_date=data_cutoff_date,
            snapshot_data=report,
            is_current=True,
        )
        self.db.add(row)
        self.db.commit()

        logger.info(
            "Investigation snapshot created case_id=%s version=%s hash=%s",
            case_id,
            next_version,
            report_hash,
        )
        return row
