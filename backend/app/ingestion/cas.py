from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.models import RawPayload
from app.storage.storage_client import StorageClient


@dataclass
class CASResult:
    checksum: str
    storage_ref: str
    is_duplicate: bool
    payload_id: Optional[int]


def checksum_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def storage_key_for_checksum(checksum: str) -> str:
    return f"raw/{checksum[:2]}/{checksum}"


def lookup_by_checksum(db: Session, checksum: str) -> Optional[RawPayload]:
    return db.query(RawPayload).filter(RawPayload.checksum == checksum).first()


def store_payload(
    db: Session,
    storage: StorageClient,
    *,
    payload: bytes,
    media_type: str | None,
    source_id: int,
    ingestion_run_id: int | None,
    provenance: dict | None = None,
) -> CASResult:
    checksum = checksum_sha256(payload)
    existing = lookup_by_checksum(db, checksum)
    if existing:
        return CASResult(
            checksum=checksum,
            storage_ref=existing.storage_ref,
            is_duplicate=True,
            payload_id=existing.payload_id,
        )

    key = storage_key_for_checksum(checksum)
    storage.put_bytes(key, payload, tier="hot", compress=False)

    row = RawPayload(
        checksum=checksum,
        storage_ref=key,
        size_bytes=len(payload),
        media_type=media_type,
        source_id=source_id,
        ingestion_run_id=ingestion_run_id,
        provenance_json=provenance or {},
    )
    db.add(row)
    db.flush()

    return CASResult(
        checksum=checksum,
        storage_ref=key,
        is_duplicate=False,
        payload_id=row.payload_id,
    )


def get_payload_bytes_by_checksum(db: Session, storage: StorageClient, checksum: str) -> Optional[bytes]:
    row = lookup_by_checksum(db, checksum)
    if not row:
        return None
    return storage.get_bytes(row.storage_ref)
