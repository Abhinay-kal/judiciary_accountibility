from __future__ import annotations

import re
from typing import Any

from app.core.config import get_settings

_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+)\b")
_ACCUSATORY_WORDS = {
    "proves": "indicates",
    "proved": "indicated",
    "guilty": "under review",
    "caused by": "pattern consistent with",
    "is responsible for": "is associated with",
}


def _normalize_labels(labels: list[str] | list[Any]) -> set[str]:
    normalized: set[str] = set()
    for label in labels or []:
        value = getattr(label, "value", label)
        normalized.add(str(value))
    return normalized


def _neutralize_verbs(text: str) -> str:
    output = text
    for src, replacement in _ACCUSATORY_WORDS.items():
        output = re.sub(re.escape(src), replacement, output, flags=re.IGNORECASE)
    return output


def _redact_names(text: str) -> tuple[str, list[str]]:
    redacted: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        redacted.append(match.group(1))
        return "a public official (name withheld pending verification)"

    return _NAME_PATTERN.sub(_replace, text), redacted


def render_public_text(
    raw_text: str,
    labels: list[str] | list[Any],
    config: dict | None = None,
    *,
    parser_confidence: float | None = None,
    source_links: list[str] | None = None,
    source_count: int | None = None,
) -> tuple[str, dict]:
    settings = get_settings()
    cfg = config or {}
    mode = str(cfg.get("defamation_mode", settings.defamation_mode)).lower()
    threshold = float(cfg.get("defamation_min_confidence_to_show_name", settings.defamation_min_confidence_to_show_name))

    normalized_labels = _normalize_labels(labels)
    text = _neutralize_verbs(raw_text or "")
    redacted_names: list[str] = []

    requires_redaction = bool({"UNVERIFIED", "REQUIRES_VERIFICATION", "DATA_ANOMALY", "SENSITIVE"} & normalized_labels)
    if mode == "strict":
        requires_redaction = True

    # Conservative legal-safe behavior: never auto-reveal names for unverified content.
    if requires_redaction:
        text, redacted_names = _redact_names(text)
    elif parser_confidence is not None and parser_confidence < threshold:
        text, redacted_names = _redact_names(text)

    status = "Verified"
    if "UNVERIFIED" in normalized_labels:
        status = "Unverified"
    elif "REQUIRES_VERIFICATION" in normalized_labels:
        status = "Requires verification"
    elif "DATA_ANOMALY" in normalized_labels:
        status = "Data anomaly"

    sources = source_count if source_count is not None else len(source_links or [])
    confidence_text = "unknown" if parser_confidence is None else f"{parser_confidence:.2f}"

    prefix = f"Data status: {status}. Sources: {sources}; parser confidence {confidence_text}."
    rendered = f"{prefix}\n{text}".strip()

    metadata = {
        "data_status": status,
        "labels": sorted(normalized_labels),
        "redacted_names": redacted_names,
        "source_links": source_links or [],
        "parser_confidence": parser_confidence,
        "mode": mode,
    }
    return rendered, metadata
