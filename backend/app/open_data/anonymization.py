from __future__ import annotations

import re
from dataclasses import dataclass


EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+91[-\s]?)?[6-9]\d{9}")
ID_PATTERN = re.compile(r"\b\d{12}\b")


SENSITIVE_KEYWORDS = {
    "address",
    "contact",
    "email",
    "phone",
    "aadhaar",
    "pan",
    "requester_name",
    "requester_contact",
    "responder_name",
    "responder_contact",
}


@dataclass(slots=True)
class AnonymizationResult:
    rows: list[dict]
    masked_fields: int


def _mask_value(value: object) -> object:
    if not isinstance(value, str):
        return value

    masked = EMAIL_PATTERN.sub("[masked-email]", value)
    masked = PHONE_PATTERN.sub("[masked-phone]", masked)
    masked = ID_PATTERN.sub("[masked-id]", masked)
    return masked


def anonymize_rows(dataset_id: str, rows: list[dict]) -> AnonymizationResult:
    masked_fields = 0
    output: list[dict] = []

    for row in rows:
        anonymized: dict = {}
        for key, value in row.items():
            lowered = key.lower()
            if any(word in lowered for word in SENSITIVE_KEYWORDS):
                anonymized[key] = "[masked]"
                masked_fields += 1
                continue

            masked_value = _mask_value(value)
            if masked_value != value:
                masked_fields += 1
            anonymized[key] = masked_value

        # Dataset-specific safeguards.
        if dataset_id in {"flagged_cases", "case_metadata", "hearing_timelines"}:
            anonymized.pop("raw_bench", None)
            anonymized.pop("outcome_text", None)
            anonymized.pop("public_note", None)

        output.append(anonymized)

    return AnonymizationResult(rows=output, masked_fields=masked_fields)
