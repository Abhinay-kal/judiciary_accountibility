from __future__ import annotations

import gzip
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from bs4 import BeautifulSoup


@dataclass
class MinimalParseResult:
    case_id: Optional[str]
    hearing_date: Optional[str]
    bench: Optional[str]
    outcome_text: Optional[str]
    order_pdf_url: Optional[str]
    full_text_gzip: bytes
    page_snippets: list[dict[str, Any]]
    parser_confidence: float
    errors: list[str]


def parse_minimal(payload: bytes, media_type: str) -> MinimalParseResult:
    if "pdf" in media_type.lower():
        return _parse_pdf(payload)
    if "json" in media_type.lower():
        return _parse_json(payload)
    return _parse_html(payload)


def _parse_html(payload: bytes) -> MinimalParseResult:
    text = payload.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "lxml")
    full_text = soup.get_text("\n", strip=True)

    case_id = _first_match(full_text, [r"case\s*id\s*[:\-]\s*([A-Za-z0-9\-/]+)", r"cnr\s*[:\-]\s*([A-Za-z0-9\-/]+)"])
    hearing_date = _first_match(full_text, [r"date\s*[:\-]\s*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})"])
    bench = _first_match(full_text, [r"bench\s*[:\-]\s*([^\n]+)"])
    outcome = _first_match(full_text, [r"outcome\s*[:\-]\s*([^\n]+)", r"order\s*[:\-]\s*([^\n]+)"])

    pdf_link = None
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if href.lower().endswith(".pdf"):
            pdf_link = href
            break

    snippets = _snippets_from_text(full_text, page_size=1200)
    confidence = _confidence(case_id, hearing_date, bench, outcome, errors=[])
    return MinimalParseResult(
        case_id=case_id,
        hearing_date=hearing_date,
        bench=bench,
        outcome_text=outcome,
        order_pdf_url=pdf_link,
        full_text_gzip=gzip.compress(full_text.encode("utf-8")),
        page_snippets=snippets,
        parser_confidence=confidence,
        errors=[],
    )


def _parse_json(payload: bytes) -> MinimalParseResult:
    errors: list[str] = []
    try:
        data = json.loads(payload)
    except Exception as exc:
        errors.append(f"json_decode_error:{exc}")
        data = {}

    if isinstance(data, list):
        row = data[0] if data else {}
    else:
        row = data

    case_id = row.get("case_id") or row.get("cnr") or row.get("case_number")
    hearing_date = row.get("date") or row.get("hearing_date")
    bench = row.get("bench")
    outcome = row.get("outcome") or row.get("outcome_text")
    pdf = row.get("order_pdf") or row.get("order_pdf_url")

    full_text = json.dumps(data, ensure_ascii=False)
    snippets = _snippets_from_text(full_text, page_size=1200)
    confidence = _confidence(case_id, hearing_date, bench, outcome, errors=errors)
    return MinimalParseResult(
        case_id=str(case_id) if case_id else None,
        hearing_date=str(hearing_date) if hearing_date else None,
        bench=str(bench) if bench else None,
        outcome_text=str(outcome) if outcome else None,
        order_pdf_url=str(pdf) if pdf else None,
        full_text_gzip=gzip.compress(full_text.encode("utf-8")),
        page_snippets=snippets,
        parser_confidence=confidence,
        errors=errors,
    )


def _parse_pdf(payload: bytes) -> MinimalParseResult:
    errors: list[str] = []
    text_pages: list[str] = []

    try:
        import fitz

        doc = fitz.open(stream=payload, filetype="pdf")
        for page in doc:
            text_pages.append(page.get_text("text") or "")
    except Exception as fitz_exc:
        errors.append(f"fitz_error:{fitz_exc}")
        try:
            from pdfminer.high_level import extract_text

            text_pages = [extract_text(io.BytesIO(payload))]
        except Exception as pdf_exc:
            errors.append(f"pdfminer_error:{pdf_exc}")
            text_pages = [""]

    full_text = "\n\n".join(text_pages)
    case_id = _first_match(full_text, [r"case\s*id\s*[:\-]\s*([A-Za-z0-9\-/]+)", r"cnr\s*[:\-]\s*([A-Za-z0-9\-/]+)"])
    hearing_date = _first_match(full_text, [r"(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})"])
    bench = _first_match(full_text, [r"bench\s*[:\-]\s*([^\n]+)", r"coram\s*[:\-]\s*([^\n]+)"])
    outcome = _first_match(full_text, [r"disposed\s+of[^\n]*", r"adjourned[^\n]*", r"listed[^\n]*"])

    snippets = [
        {"page": i + 1, "snippet": (page_text or "")[:600]}
        for i, page_text in enumerate(text_pages)
    ]
    confidence = _confidence(case_id, hearing_date, bench, outcome, errors=errors)

    return MinimalParseResult(
        case_id=case_id,
        hearing_date=hearing_date,
        bench=bench,
        outcome_text=outcome,
        order_pdf_url=None,
        full_text_gzip=gzip.compress(full_text.encode("utf-8")),
        page_snippets=snippets,
        parser_confidence=confidence,
        errors=errors,
    )


def _first_match(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip() if m.groups() else m.group(0).strip()
    return None


def _snippets_from_text(text: str, page_size: int = 1200) -> list[dict[str, Any]]:
    if not text:
        return []
    chunks = [text[i : i + page_size] for i in range(0, len(text), page_size)]
    return [{"page": i + 1, "snippet": chunk[:600]} for i, chunk in enumerate(chunks)]


def _confidence(case_id: Optional[str], hearing_date: Optional[str], bench: Optional[str], outcome: Optional[str], *, errors: list[str]) -> float:
    required = [bool(case_id), bool(hearing_date), bool(bench), bool(outcome)]
    base = sum(required) / 4.0
    penalty = min(0.4, 0.1 * len(errors))
    return max(0.0, min(1.0, base - penalty))
