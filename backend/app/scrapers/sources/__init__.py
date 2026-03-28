from app.scrapers.sources.ecourts import ECourtsScraper
from app.scrapers.sources.high_court import HighCourtCauseListScraper
from app.scrapers.sources.india_sources import INDIA_SOURCE_SCRAPERS
from app.scrapers.sources.njdg import NJDGScraper
from app.scrapers.sources.supreme_court import SupremeCourtCauseListScraper

__all__ = [
    "NJDGScraper",
    "ECourtsScraper",
    "HighCourtCauseListScraper",
    "SupremeCourtCauseListScraper",
    "INDIA_SOURCE_SCRAPERS",
]
