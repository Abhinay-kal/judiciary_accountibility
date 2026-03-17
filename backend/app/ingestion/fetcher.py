from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from app.ingestion.config import IngestionSettings, get_ingestion_settings
from app.ingestion.models import IngestionSource

logger = logging.getLogger(__name__)


class FetchExhaustedError(RuntimeError):
    pass


@dataclass
class FetchResult:
    status_code: int
    body: bytes
    etag: Optional[str]
    last_modified: Optional[str]
    not_modified: bool
    fetched_at: datetime
    strategy: str


class DeltaFetcher:
    """HEAD-first fetcher with conditional requests and retry/backoff.

    Ethical policy:
    - This client intentionally does not bypass CAPTCHAs, auth gates, or anti-bot controls.
    - If a source blocks automated access, operators must use contact-first channels
      (official API request / admin permission / RTI route) and fallback to manual ingestion.
    """

    def __init__(self, settings: Optional[IngestionSettings] = None, timeout: int = 30) -> None:
        self.settings = settings or get_ingestion_settings()
        self.timeout = timeout
        self.session = requests.Session()

    def fetch(self, source: IngestionSource) -> FetchResult:
        if not source.base_url:
            raise ValueError(f"Source {source.source_name} has no base_url")

        self._respect_robots(source.base_url)
        self._enforce_rate_limit(source)

        headers: dict[str, str] = {}
        cfg = source.config_json or {}
        prev_etag = cfg.get("etag")
        prev_last_modified = cfg.get("last_modified")
        if prev_etag:
            headers["If-None-Match"] = prev_etag
        if prev_last_modified:
            headers["If-Modified-Since"] = prev_last_modified

        head_resp = self._request_with_backoff("HEAD", source.base_url, headers=headers)

        # If server supports conditional HEAD and confirms unchanged payload.
        if head_resp.status_code == 304:
            return FetchResult(
                status_code=304,
                body=b"",
                etag=prev_etag,
                last_modified=prev_last_modified,
                not_modified=True,
                fetched_at=datetime.now(timezone.utc),
                strategy="head_304",
            )

        current_etag = head_resp.headers.get("ETag")
        current_last_modified = head_resp.headers.get("Last-Modified")

        # HEAD says ETag unchanged even without 304 semantics.
        if current_etag and prev_etag and current_etag == prev_etag:
            return FetchResult(
                status_code=200,
                body=b"",
                etag=current_etag,
                last_modified=current_last_modified or prev_last_modified,
                not_modified=True,
                fetched_at=datetime.now(timezone.utc),
                strategy="head_etag_match",
            )

        if current_last_modified and prev_last_modified:
            try:
                cur_dt = parsedate_to_datetime(current_last_modified)
                prev_dt = parsedate_to_datetime(prev_last_modified)
                if cur_dt <= prev_dt:
                    return FetchResult(
                        status_code=200,
                        body=b"",
                        etag=current_etag,
                        last_modified=current_last_modified,
                        not_modified=True,
                        fetched_at=datetime.now(timezone.utc),
                        strategy="head_last_modified_match",
                    )
            except Exception:
                pass

        # Fallback to GET, still conditional when available.
        get_resp = self._request_with_backoff("GET", source.base_url, headers=headers)
        if get_resp.status_code == 304:
            return FetchResult(
                status_code=304,
                body=b"",
                etag=prev_etag,
                last_modified=prev_last_modified,
                not_modified=True,
                fetched_at=datetime.now(timezone.utc),
                strategy="get_304",
            )

        return FetchResult(
            status_code=get_resp.status_code,
            body=get_resp.content,
            etag=get_resp.headers.get("ETag") or current_etag,
            last_modified=get_resp.headers.get("Last-Modified") or current_last_modified,
            not_modified=False,
            fetched_at=datetime.now(timezone.utc),
            strategy="get_full",
        )

    def _request_with_backoff(self, method: str, url: str, headers: Optional[dict[str, str]] = None) -> requests.Response:
        retry_limit = self.settings.ingest_retry_limit
        base = self.settings.ingest_backoff_base_seconds
        last_exc: Exception | None = None

        for attempt in range(retry_limit + 1):
            try:
                resp = self.session.request(method, url, headers=headers, timeout=self.timeout)
                if resp.status_code in (429, 503):
                    if attempt >= retry_limit:
                        raise FetchExhaustedError(f"{method} {url} exhausted after {retry_limit} retries, status={resp.status_code}")
                    sleep_seconds = base * (2**attempt)
                    logger.warning("Retrying %s %s after status=%s in %ss", method, url, resp.status_code, sleep_seconds)
                    time.sleep(sleep_seconds)
                    continue
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= retry_limit:
                    raise FetchExhaustedError(f"{method} {url} failed after {retry_limit} retries") from exc
                sleep_seconds = base * (2**attempt)
                time.sleep(sleep_seconds)
        raise FetchExhaustedError(f"{method} {url} failed") from last_exc

    def _respect_robots(self, url: str) -> None:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            if not rp.can_fetch("*", url):
                raise PermissionError(f"robots.txt disallows fetch for {url}")
        except PermissionError:
            raise
        except Exception:
            # If robots cannot be read due to transient network issues, proceed cautiously.
            logger.warning("Could not validate robots.txt for %s", url)

    def _enforce_rate_limit(self, source: IngestionSource) -> None:
        cfg = source.config_json or {}
        rate_limit = float(cfg.get("rate_limit_seconds", 0.0))
        if rate_limit <= 0 and source.expected_update_interval_minutes:
            # Conservative fallback: no per-request throttle by interval; clamp to 1s.
            rate_limit = 1.0
        if rate_limit > 0:
            time.sleep(rate_limit)
