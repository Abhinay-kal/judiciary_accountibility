from __future__ import annotations

from datetime import datetime
from typing import Any


def build_share_metadata(report: dict[str, Any], *, canonical_url: str) -> dict[str, Any]:
    findings = report.get("anomalies", [])
    top_findings = [item.get("title") for item in findings[:3] if item.get("title")]
    summary = report.get("summary", {}).get("narrative") or "Investigation report"
    title = report.get("summary", {}).get("headline") or f"Case investigation #{report.get('case_id')}"
    updated = report.get("last_updated") or datetime.utcnow().isoformat()

    return {
        "title": title,
        "summary": summary,
        "key_findings": top_findings,
        "updated_time": updated,
        "open_graph": {
            "og:title": title,
            "og:description": summary,
            "og:type": "article",
            "og:url": canonical_url,
            "article:modified_time": updated,
        },
        "twitter_card": {
            "twitter:card": "summary_large_image",
            "twitter:title": title,
            "twitter:description": summary,
        },
        "schema_org": {
            "@context": "https://schema.org",
            "@type": "Report",
            "name": title,
            "description": summary,
            "url": canonical_url,
            "dateModified": updated,
            "about": {
                "@type": "LegalCase",
                "identifier": str(report.get("case_id")),
                "name": report.get("summary", {}).get("case_number") or str(report.get("case_id")),
            },
            "keywords": [
                "judiciary",
                "case delay",
                "investigation",
            ],
        },
    }
