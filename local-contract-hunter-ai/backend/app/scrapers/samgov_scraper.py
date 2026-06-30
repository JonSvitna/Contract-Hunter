from __future__ import annotations

import time
from datetime import datetime, timedelta

import requests

from app.config import settings
from app.scrapers.base_scraper import BaseScraper


SAM_GOV_API_URL = "https://api.sam.gov/opportunities/v2/search"

# NAICS codes covering cybersecurity and CMMC-adjacent work
NAICS_CODES = [
    "541519",  # Other Computer Related Services
    "541512",  # Computer Systems Design Services
    "541690",  # Other Scientific and Technical Consulting Services
    "541330",  # Engineering Services
]

# Keyword pass — supplements NAICS to catch CMMC-specific language
CMMC_KEYWORDS = [
    "CMMC",
    "cybersecurity maturity model",
    "information security",
    "cyber security assessment",
    "NIST 800-171",
    "zero trust",
    "vulnerability assessment",
    "penetration testing",
]


class SamGovScraper(BaseScraper):
    """
    Pulls federal contract opportunities from the SAM.gov Opportunities v2 API.
    Uses the registered API key for higher rate limits (up to 1,000 req/hour).
    No browser required — pure HTTP.
    """

    def __init__(self, delay_seconds: float = 1.0, max_pages: int = 5):
        self.delay_seconds = delay_seconds
        self.max_pages = max_pages

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        if not settings.sam_gov_api_key:
            return []

        posted_from = (datetime.utcnow() - timedelta(days=90)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")

        results: list[dict] = []
        seen_ids: set[str] = set()

        # Pass 1: search by NAICS code
        for naics in NAICS_CODES:
            self._fetch_pages(
                params_base={
                    "naics": naics,
                    "postedFrom": posted_from,
                    "postedTo": posted_to,
                    "ptype": "sol,presol",
                    "limit": 100,
                },
                source_name=source_name,
                source_url=source_url,
                results=results,
                seen_ids=seen_ids,
            )

        # Pass 2: CMMC / keyword search — catches solicitations filed under other NAICS
        for keyword in CMMC_KEYWORDS:
            self._fetch_pages(
                params_base={
                    "q": keyword,
                    "postedFrom": posted_from,
                    "postedTo": posted_to,
                    "ptype": "sol,presol",
                    "limit": 100,
                },
                source_name=source_name,
                source_url=source_url,
                results=results,
                seen_ids=seen_ids,
            )

        return results

    def _fetch_pages(
        self,
        params_base: dict,
        source_name: str,
        source_url: str,
        results: list[dict],
        seen_ids: set[str],
    ) -> None:
        limit = params_base.get("limit", 100)
        offset = 0

        for _ in range(self.max_pages):
            params = {
                "api_key": settings.sam_gov_api_key,
                "offset": offset,
                **params_base,
            }
            try:
                resp = requests.get(SAM_GOV_API_URL, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break

            opps = data.get("opportunitiesData") or []
            if not opps:
                break

            for opp in opps:
                notice_id = opp.get("noticeId") or opp.get("solicitationNumber") or ""
                if notice_id and notice_id in seen_ids:
                    continue
                if notice_id:
                    seen_ids.add(notice_id)

                due_date = None
                raw_deadline = opp.get("responseDeadLine") or opp.get("archiveDate")
                if raw_deadline:
                    try:
                        due_date = datetime.strptime(raw_deadline[:10], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                agency = (
                    opp.get("subtierName")
                    or opp.get("departmentName")
                    or source_name
                )

                opp_url = opp.get("uiLink")
                if not opp_url and notice_id:
                    opp_url = f"https://sam.gov/opp/{notice_id}/view"

                results.append({
                    "title": (opp.get("title") or "")[:500],
                    "agency": agency[:255],
                    "source_name": source_name,
                    "source_url": source_url,
                    "opportunity_url": opp_url,
                    "external_id": notice_id[:255] if notice_id else None,
                    "source_status": (opp.get("baseType") or opp.get("typeOfNotice") or "")[:100],
                    "due_date": due_date,
                    "description_snippet": (opp.get("description") or "")[:2000],
                    "extraction_confidence": 0.92,
                    "manual_review_needed": False,
                })

            total = data.get("totalRecords", 0)
            offset += limit
            if offset >= total:
                break

            time.sleep(self.delay_seconds)
