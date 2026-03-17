from __future__ import annotations

from io import BytesIO

import fitz
from pdfminer.high_level import extract_text


def extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF bytes with PyMuPDF and fallback to pdfminer."""

    try:
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return extract_text(BytesIO(content))
