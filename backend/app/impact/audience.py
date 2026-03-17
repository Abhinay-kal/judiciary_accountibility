from __future__ import annotations

SUPPORTED_AUDIENCES = {
    "journalists",
    "policymakers",
    "legal_professionals",
    "civil_society",
    "general_public",
}


def normalize_audience(value: str | None) -> str:
    if not value:
        return "general_public"
    slug = value.strip().lower()
    return slug if slug in SUPPORTED_AUDIENCES else "general_public"


def adapt_executive_summary(*, audience: str, base_summary: str) -> str:
    if audience == "journalists":
        return base_summary + " Source-backed framing supports responsible public-interest reporting."
    if audience == "policymakers":
        return base_summary + " This pattern can inform administrative and process-efficiency review."
    if audience == "legal_professionals":
        return base_summary + " Timeline benchmarks may help procedural planning and client advisories."
    if audience == "civil_society":
        return base_summary + " Verified trend reporting can strengthen constructive transparency efforts."
    return base_summary


def policymaker_note() -> str:
    return "Use this case alongside court-level aggregates to prioritize procedural bottlenecks, not individual attribution."
