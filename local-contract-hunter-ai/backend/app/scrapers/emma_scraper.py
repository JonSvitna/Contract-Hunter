from __future__ import annotations

from app.scrapers.generic_procurement_scraper import GenericProcurementScraper


class EmmaScraper(GenericProcurementScraper):
    """MVP eMMA scraper built on top of generic logic to avoid brittle selectors."""
