from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper


class SupremeCourtCauseListScraper(BaseScraper):
    source_name = "supreme_court"

    def run(self) -> list[tuple]:
        urls = [
            "https://www.sci.gov.in/",
            "https://main.sci.gov.in/causelists",
        ]
        output = []
        for raw in self.fetch_urls(urls):
            for record in self.parse(raw):
                output.append((raw, record))
        return output

    def parse(self, raw):
        soup = BeautifulSoup(raw.content, "lxml")
        title = soup.title.text.strip() if soup.title else "Supreme Court Cause List"
        return [
            {
                "case_uid": f"supreme::{raw.checksum[:16]}",
                "case_number": title,
                "court_name": "Supreme Court of India",
                "court_level": "supreme",
                "state": "National",
                "status": "pending",
                "source_url": raw.url,
                "source_fields": {"source": "supreme_court"},
                "hearings": [
                    {
                        "date": date.today(),
                        "listing_type": "cause_list",
                        "raw_bench": title,
                        "raw_outcome_text": None,
                        "outcome_text": None,
                    }
                ],
            }
        ]
