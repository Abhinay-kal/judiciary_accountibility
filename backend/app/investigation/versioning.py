from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Remove ephemeral keys before hashing to keep content hashes stable."""

    return {
        "case_id": report.get("case_id"),
        "summary": report.get("summary"),
        "timeline": report.get("timeline", []),
        "metrics": report.get("metrics", {}),
        "anomalies": report.get("anomalies", []),
        "evidence": report.get("evidence", []),
        "methodology": report.get("methodology", {}),
        "confidence": report.get("confidence", {}),
        "right_to_respond": report.get("right_to_respond", {}),
        "disclaimer": report.get("disclaimer"),
    }


def compute_content_hash(report: dict[str, Any]) -> str:
    payload = stable_report_payload(report)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def next_version_number(current_version: int | None) -> int:
    if current_version is None:
        return 1
    return int(current_version) + 1
