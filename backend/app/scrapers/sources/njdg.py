from __future__ import annotations

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper


class NJDGScraper(BaseScraper):
    source_name = "njdg"

    def run(self) -> list[tuple]:
        urls = [
            "https://njdg.ecourts.gov.in/njdgnew/index.php",
        ]
        output = []
        for url in urls:
            raw = self.fetch_url(url)
            for record in self.parse(raw):
                output.append((raw, record))
        return output

    def parse(self, raw):
        soup = BeautifulSoup(raw.content, "lxml")
        title = soup.title.text.strip() if soup.title else "NJDG"
        return [
            {
                "case_uid": f"njdg::{raw.checksum[:16]}",
                "case_number": title,
                "court_name": "Unknown NJDG Court",
                "court_level": "district",
                "state": "Unknown",
                "status": "pending",
                "source_url": raw.url,
                "source_fields": {"source": "njdg"},
            }
        ]
