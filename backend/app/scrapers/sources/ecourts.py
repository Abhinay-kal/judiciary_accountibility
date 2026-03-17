from __future__ import annotations

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper


class ECourtsScraper(BaseScraper):
    source_name = "ecourts"

    def run(self) -> list[tuple]:
        urls = [
            "https://services.ecourts.gov.in/ecourtindia_v6/",
        ]
        output = []
        for url in urls:
            raw = self.fetch_url(url)
            for record in self.parse(raw):
                output.append((raw, record))
        return output

    def parse(self, raw):
        soup = BeautifulSoup(raw.content, "lxml")
        heading = soup.find("h1")
        title = heading.text.strip() if heading else "eCourts"
        return [
            {
                "case_uid": f"ecourts::{raw.checksum[:16]}",
                "case_number": title,
                "court_name": "eCourts Registry",
                "court_level": "district",
                "state": "Unknown",
                "status": "pending",
                "source_url": raw.url,
                "source_fields": {"source": "ecourts"},
            }
        ]
