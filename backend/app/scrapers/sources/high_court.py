from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.utils.pdf_parser import extract_pdf_text


class HighCourtCauseListScraper(BaseScraper):
    source_name = "high_court"

    def run(self) -> list[tuple]:
        html_urls = [
            "https://www.allahabadhighcourt.in/",
        ]
        pdf_urls = [
            "https://main.sci.gov.in/pdf/causelist/sample.pdf",
        ]
        output = []
        for raw in self.fetch_urls(html_urls):
            for record in self.parse(raw):
                output.append((raw, record))

        try:
            for raw_pdf in self.fetch_urls(pdf_urls):
                for record in self.parse(raw_pdf):
                    output.append((raw_pdf, record))
        except Exception:
            pass
        return output

    def parse(self, raw):
        if raw.url.lower().endswith(".pdf"):
            text = extract_pdf_text(raw.content)
            marker = text[:100].strip() if text else "High Court PDF Cause List"
            return [
                {
                    "case_uid": f"highcourt::{raw.checksum[:16]}",
                    "case_number": marker,
                    "court_name": "High Court",
                    "court_level": "high",
                    "state": "Unknown",
                    "status": "pending",
                    "source_url": raw.url,
                    "source_fields": {"source": "high_court_pdf"},
                    "hearings": [
                        {
                            "date": date.today(),
                            "listing_type": "cause_list",
                            "raw_bench": marker,
                            "outcome_text": None,
                        }
                    ],
                }
            ]

        soup = BeautifulSoup(raw.content, "lxml")
        title = soup.title.text.strip() if soup.title else "High Court Cause List"
        return [
            {
                "case_uid": f"highcourt::{raw.checksum[:16]}",
                "case_number": title,
                "court_name": "High Court",
                "court_level": "high",
                "state": "Unknown",
                "status": "pending",
                "source_url": raw.url,
                "source_fields": {"source": "high_court_html"},
                "hearings": [
                    {
                        "date": date.today(),
                        "listing_type": "cause_list",
                        "raw_bench": title,
                        "outcome_text": None,
                    }
                ],
            }
        ]
