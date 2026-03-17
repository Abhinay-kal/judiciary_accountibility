from __future__ import annotations

import re
from dataclasses import dataclass

HIGH_RISK_KEYWORDS = [
    "bribe",
    "corrupt",
    "corruption",
    "fraud",
    "embezzle",
    "molestation",
    "money laundering",
    "kickback",
    "scam",
]

ACCUSATORY_PATTERNS = [
    re.compile(r"\\b(is|was|are)\\s+(guilty|corrupt|fraudulent)\\b", re.IGNORECASE),
    re.compile(r"\\b(took|accepted)\\s+(a\\s+)?bribe\\b", re.IGNORECASE),
    re.compile(r"\\bcommitted\\s+(fraud|embezzlement|molestation)\\b", re.IGNORECASE),
]


@dataclass
class RiskPhraseCheck:
    has_high_risk_language: bool
    matched_keywords: list[str]
    matched_patterns: list[str]
    accusation_score: float


def detect_risky_phrasing(text: str) -> RiskPhraseCheck:
    lowered = (text or "").lower()
    matched_keywords = [keyword for keyword in HIGH_RISK_KEYWORDS if keyword in lowered]

    matched_patterns: list[str] = []
    for pattern in ACCUSATORY_PATTERNS:
        if pattern.search(text or ""):
            matched_patterns.append(pattern.pattern)

    score = min(1.0, (0.2 * len(matched_keywords)) + (0.4 * len(matched_patterns)))
    return RiskPhraseCheck(
        has_high_risk_language=bool(matched_keywords or matched_patterns),
        matched_keywords=matched_keywords,
        matched_patterns=matched_patterns,
        accusation_score=round(score, 4),
    )


def has_primary_source_link(evidence_bundle: dict | None) -> bool:
    if not evidence_bundle:
        return False
    links = evidence_bundle.get("source_links") or []
    return any(str(link).startswith(("http://", "https://")) for link in links)
