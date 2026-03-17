from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ScrapeResult:
    source: str
    url: str
    content: bytes
    content_type: str
    checksum: str
    raw_storage_path: str


class BaseScraper:
    """Base class for resilient, rate-limited, retry-safe scraping."""

    source_name: str = "base"

    def __init__(self) -> None:
        self.session = requests.Session()
        retries = Retry(
            total=settings.scraper_max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def fetch_url(self, url: str) -> ScrapeResult:
        """Fetch URL and persist raw response for auditability."""

        headers = {"User-Agent": settings.scraper_user_agent}
        response = self.session.get(url, headers=headers, timeout=settings.scraper_timeout_seconds)
        response.raise_for_status()

        content = response.content
        checksum = hashlib.sha256(content).hexdigest()
        raw_storage_path = self._store_raw(url, content, checksum)
        time.sleep(settings.scraper_rate_limit_seconds)

        logger.info("Fetched %s (%s)", url, checksum)

        return ScrapeResult(
            source=self.source_name,
            url=url,
            content=content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            checksum=checksum,
            raw_storage_path=raw_storage_path,
        )

    def _store_raw(self, url: str, content: bytes, checksum: str) -> str:
        """Persist raw payloads to disk for auditing and reproducibility."""

        out_dir = Path("raw_data") / self.source_name
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".html"
        if url.lower().endswith(".pdf"):
            suffix = ".pdf"
        file_path = out_dir / f"{checksum}{suffix}"
        if not file_path.exists():
            file_path.write_bytes(content)
        return str(file_path)

    def parse(self, raw: ScrapeResult) -> list[dict[str, Any]]:
        """Parse raw response into normalized dictionaries."""

        raise NotImplementedError

    def run(self) -> list[tuple[ScrapeResult, dict[str, Any]]]:
        """Run scraper and return raw + parsed records."""

        raise NotImplementedError
