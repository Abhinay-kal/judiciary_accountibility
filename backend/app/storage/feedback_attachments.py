from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.storage.storage_client import StorageClient

_TAG_RE = re.compile(r"<[^>]+>")


class AttachmentSecurityError(ValueError):
    pass


def scan_attachment(filename: str, payload: bytes) -> dict:
    lowered = filename.lower()
    if lowered.endswith((".exe", ".js", ".sh", ".bat")):
        raise AttachmentSecurityError("Unsupported executable attachment type")
    checksum = hashlib.sha256(payload).hexdigest()
    return {"status": "clean", "checksum": checksum}


def strip_attachment_metadata(filename: str, payload: bytes) -> bytes:
    # Stub for metadata stripping. Wire exiftool or dedicated parser in production.
    return payload


def extract_attachment_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".json"}:
        try:
            return payload.decode("utf-8", errors="replace")[:4000]
        except Exception:
            return ""
    return ""


def sanitize_html_text(raw_text: str) -> str:
    text = (raw_text or "").replace("\x00", "")
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    text = _TAG_RE.sub("", text)
    return text.strip()


def store_feedback_attachments(
    storage: StorageClient,
    *,
    feedback_id: str,
    attachments: Iterable[tuple[str, bytes]],
    is_public: bool,
) -> list[dict]:
    refs: list[dict] = []
    for filename, payload in attachments:
        scan = scan_attachment(filename, payload)
        clean = strip_attachment_metadata(filename, payload)
        extracted = extract_attachment_text(filename, clean)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        key = f"feedback/{feedback_id}/{ts}_{Path(filename).name}"
        storage.put_bytes(key, clean, tier="hot", compress=False)
        refs.append(
            {
                "storage_ref": key,
                "filename": Path(filename).name,
                "size_bytes": len(clean),
                "scan_status": scan["status"],
                "checksum": scan["checksum"],
                "ocr_text_snippet": extracted[:500],
                "public": bool(is_public),
            }
        )
    return refs
