from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup

from app.ingestion.source_specs import GENERIC_HTML_SOURCE_SPECS
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


def _to_class_name(source_name: str) -> str:
    parts = [p for p in source_name.split("_") if p]
    return "".join(part.capitalize() for part in parts) + "Scraper"


def _build_generic_scraper(spec: dict[str, str | int]):
    source_name = str(spec["source_name"])
    base_url = str(spec["base_url"])
    court_name = str(spec["court_name"])
    court_level = str(spec["court_level"])
    state = str(spec["state"])

    class GenericHtmlSourceScraper(BaseScraper):
        source_name = "generic_html"
        _base_url = ""
        _court_name = ""
        _court_level = "high"
        _state = "Unknown"

        def run(self) -> list[tuple]:
            output: list[tuple] = []
            try:
                raw = self.fetch_url(self._base_url)
                logger.info("[%s] fetched %s", self.source_name, self._base_url)
                records = self.parse(raw)
                if not records:
                    logger.warning("[%s] no records parsed, creating placeholder", self.source_name)
                    records = [self._placeholder_record(raw)]
                for record in records:
                    output.append((raw, record))
                logger.info("[%s] parsed %d records", self.source_name, len(records))
            except TimeoutError:
                logger.warning("[%s] timeout fetching %s", self.source_name, self._base_url)
            except Exception as exc:
                logger.error("[%s] fetch/parse error: %s", self.source_name, exc)
            return output

        def parse(self, raw):
            try:
                soup = BeautifulSoup(raw.content, "lxml")
                records: list[dict] = []

                # Common patterns for court listings; keep heuristic minimal but useful.
                case_nodes = soup.find_all(
                    ["tr", "div", "li"],
                    class_=["case", "cause", "listing", "row", "case-row", "entry"],
                )
                for node in case_nodes[:40]:
                    text = node.get_text(strip=True)
                    if text and len(text) > 10:
                        records.append(
                            {
                                "case_uid": f"{self.source_name}::{text[:30]}::{raw.checksum[:8]}",
                                "case_number": text[:120],
                                "court_name": self._court_name,
                                "court_level": self._court_level,
                                "state": self._state,
                                "status": "pending",
                                "source_url": raw.url,
                                "source_fields": {"source": self.source_name},
                                "hearings": [
                                    {
                                        "date": date.today(),
                                        "listing_type": "cause_list",
                                        "raw_bench": text[:120],
                                        "raw_outcome_text": None,
                                        "outcome_text": None,
                                    }
                                ],
                            }
                        )

                if not records:
                    records.append(self._placeholder_record(raw))
                return records
            except Exception as exc:
                logger.warning("[%s] parse error: %s", self.source_name, exc)
                return []

        def _placeholder_record(self, raw) -> dict:
            soup = BeautifulSoup(raw.content, "lxml")
            title = soup.title.text.strip() if soup.title else self._court_name
            now = datetime.now(timezone.utc)
            ts = now.strftime("%Y%m%d%H%M%S")
            # Include timestamp to avoid unique constraint violations on retries
            case_num = f"[PLACEHOLDER {ts}] {title[:80]}"
            return {
                "case_uid": f"{self.source_name}::placeholder::{ts}::{raw.checksum[:8]}",
                "case_number": case_num,
                "court_name": self._court_name,
                "court_level": self._court_level,
                "state": self._state,
                "status": "pending",
                "source_url": raw.url,
                "source_fields": {"source": self.source_name},
                "hearings": [
                    {
                        "date": date.today(),
                        "listing_type": "cause_list",
                        "raw_bench": title[:120],
                        "raw_outcome_text": None,
                        "outcome_text": None,
                    }
                ],
            }

    GenericHtmlSourceScraper.source_name = source_name
    GenericHtmlSourceScraper._base_url = base_url
    GenericHtmlSourceScraper._court_name = court_name
    GenericHtmlSourceScraper._court_level = court_level
    GenericHtmlSourceScraper._state = state
    GenericHtmlSourceScraper.__name__ = _to_class_name(source_name)
    return GenericHtmlSourceScraper


INDIA_SOURCE_SCRAPERS: dict[str, type[BaseScraper]] = {
    str(spec["source_name"]): _build_generic_scraper(spec) for spec in GENERIC_HTML_SOURCE_SPECS
}


__all__ = ["INDIA_SOURCE_SCRAPERS"]
