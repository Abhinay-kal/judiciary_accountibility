from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.ingestion.metrics import SCRAPER_SCHEMA_DRIFT_TOTAL
from app.schemas.ingestion_boundary import RawHearingPayload

logger = logging.getLogger(__name__)


def _quarantine_directory() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    directory = backend_root / "raw_data" / "quarantine"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_source_label(raw_record: dict) -> str:
    for key in ("court_id", "source", "court_name"):
        value = raw_record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "unknown"


def _resolve_case_identifier(raw_record: dict) -> str:
    for key in ("case_uid", "case_number", "cnr"):
        value = raw_record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "unknown_case"


def _quarantine_payload(raw_record: dict, validation_error: ValidationError, record_index: int) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    case_id = _resolve_case_identifier(raw_record)
    safe_case_id = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in case_id)
    file_path = _quarantine_directory() / f"{timestamp}_{record_index}_{safe_case_id}.json"

    serialized = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "validation_errors": validation_error.errors(),
        "raw_payload": raw_record,
    }
    file_path.write_text(json.dumps(serialized, default=str, ensure_ascii=True, indent=2), encoding="utf-8")


def validate_and_route_ingestion_batch(raw_scraped_data_list: list[dict]) -> list[RawHearingPayload]:
    validated_payloads: list[RawHearingPayload] = []

    for index, raw_record in enumerate(raw_scraped_data_list):
        try:
            payload = RawHearingPayload.model_validate(raw_record)
            validated_payloads.append(payload)
        except ValidationError as exc:
            source_label = _resolve_source_label(raw_record)
            case_identifier = _resolve_case_identifier(raw_record)

            SCRAPER_SCHEMA_DRIFT_TOTAL.labels(source=source_label).inc()
            logger.critical(
                "SCRAPER_SCHEMA_DRIFT source=%s case=%s validation_errors=%s",
                source_label,
                case_identifier,
                exc.errors(),
            )

            try:
                _quarantine_payload(raw_record, exc, index)
            except Exception:
                logger.exception(
                    "Failed to quarantine invalid ingestion row source=%s case=%s",
                    source_label,
                    case_identifier,
                )

    return validated_payloads