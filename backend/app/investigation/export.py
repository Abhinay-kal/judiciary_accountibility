from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from app.investigation.renderer import render_investigation_html


def export_json_package(report: dict[str, Any], *, snapshot_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot": snapshot_meta,
        "report": report,
    }


def export_printable_html(report: dict[str, Any], *, canonical_url: str, version_number: int) -> str:
    return render_investigation_html(report, canonical_url=canonical_url, version_number=version_number)


def export_pdf_bytes(report: dict[str, Any], *, snapshot_meta: dict[str, Any]) -> bytes:
    """Create a lightweight single-page PDF without external dependencies."""

    lines = [
        "Court Case Delay and Justice Tracker - Investigation Report",
        f"Case ID: {report.get('case_id')}",
        f"Version: {snapshot_meta.get('version_number')}",
        f"Generated: {snapshot_meta.get('generated_at')}",
        "",
        "Summary:",
        str(report.get("summary", {}).get("narrative") or ""),
        "",
        "Key Metrics:",
        f"- Total duration (years): {report.get('metrics', {}).get('total_duration_years')}",
        f"- Percentile rank: {report.get('metrics', {}).get('percentile_ranking')}",
        f"- Strategic delay score: {report.get('metrics', {}).get('strategic_delay_score')}",
        "",
        "Disclaimer:",
        str(report.get("disclaimer") or ""),
    ]

    content = "\\n".join(lines).replace("(", "[").replace(")", "]")
    text_stream = f"BT /F1 10 Tf 40 760 Td ({content}) Tj ET"

    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(text_stream)} >> stream\n{text_stream}\nendstream endobj\n",
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    body = "%PDF-1.4\n"
    xref_positions = []
    for obj in objects:
        xref_positions.append(len(body.encode("utf-8")))
        body += obj

    xref_start = len(body.encode("utf-8"))
    xref = ["xref\n0 6\n0000000000 65535 f "]
    for pos in xref_positions:
        xref.append(f"{pos:010d} 00000 n ")
    trailer = "\ntrailer << /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_start) + "\n%%EOF\n"
    pdf = body + "\n".join(xref) + trailer
    return pdf.encode("utf-8")


def export_offline_archive(
    report: dict[str, Any],
    *,
    canonical_url: str,
    version_number: int,
    snapshot_meta: dict[str, Any],
) -> bytes:
    html = export_printable_html(report, canonical_url=canonical_url, version_number=version_number)
    json_payload = json.dumps(export_json_package(report, snapshot_meta=snapshot_meta), indent=2, default=str)
    source_lines = [item.get("source_url", "") for item in report.get("evidence", [])]
    sources = "\n".join([line for line in source_lines if line])

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.html", html)
        archive.writestr("report.json", json_payload)
        archive.writestr("sources.txt", sources)
    return output.getvalue()
