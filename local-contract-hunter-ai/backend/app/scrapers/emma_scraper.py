from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from app.scrapers.base_scraper import BaseScraper
from app.services.extraction_service import (
    confidence_from_text,
    parse_possible_due_date,
    snippet_with_keywords,
)

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


EMMA_SOLICITATION_PATTERNS = [
    "bpm",
    "bid",
    "sourcing",
    "solicitation",
    "process_manage_extranet",
    "request_browse_public",
]


def _looks_like_emma_opportunity(text: str, href: str, keywords: list[str]) -> bool:
    lowered_text = text.lower()
    lowered_href = href.lower()
    if any(nav in lowered_text for nav in ["login", "register", "help", "training", "contact"]):
        return False
    has_emma_pattern = any(pattern in lowered_href or pattern in lowered_text for pattern in EMMA_SOLICITATION_PATTERNS)
    has_keyword = any(keyword.lower() in lowered_text for keyword in keywords)
    return has_emma_pattern and has_keyword


def _agency_from_text(text: str, source_name: str) -> str:
    match = re.search(r"(Maryland [A-Za-z0-9&.,' -]+?)(?: Due Date:| Closing Date:|$)", text)
    if match:
        return match.group(1).strip()
    return source_name


def normalize_emma_anchor(
    source_name: str,
    source_url: str,
    text: str,
    href: str,
    keywords: list[str],
) -> dict | None:
    cleaned_text = " ".join(text.split())
    if not cleaned_text or not href:
        return None
    if not _looks_like_emma_opportunity(cleaned_text, href, keywords):
        return None

    opportunity_url = urljoin(source_url, href)
    return {
        "title": cleaned_text[:500],
        "agency": _agency_from_text(cleaned_text, source_name),
        "source_name": source_name,
        "source_url": source_url,
        "opportunity_url": opportunity_url,
        "due_date": parse_possible_due_date(cleaned_text),
        "description_snippet": snippet_with_keywords(cleaned_text, keywords),
        "extraction_confidence": confidence_from_text(cleaned_text, keywords),
        "manual_review_needed": False,
    }


class EmmaScraper(BaseScraper):
    def __init__(
        self,
        delay_seconds: float = 2.0,
        max_candidate_links: int = 120,
        page_timeout_ms: int = 20000,
        body_timeout_ms: int = 5000,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.max_candidate_links = max_candidate_links
        self.page_timeout_ms = page_timeout_ms
        self.body_timeout_ms = body_timeout_ms

    def manual_review_result(self, source_name: str, source_url: str, reason: str) -> dict:
        return {
            "title": f"Manual review needed for {source_name}",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": reason,
            "extraction_confidence": 0.2,
            "manual_review_needed": True,
        }

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        if sync_playwright is None:
            return [
                self.manual_review_result(
                    source_name,
                    source_url,
                    "Playwright is not installed locally. eMMA source retained for manual review.",
                )
            ]

        results: list[dict] = []
        with sync_playwright() as p:
            browser = None
            context = None
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto(source_url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
                time.sleep(self.delay_seconds)
                page_text = page.locator("body").inner_text(timeout=self.body_timeout_ms)
                anchors = page.eval_on_selector_all(
                    "a",
                    "(elements, limit) => elements.slice(0, limit).map(e => ({href: e.href || '', text: (e.innerText || e.textContent || '').trim()}))",
                    self.max_candidate_links,
                )

                for anchor in anchors:
                    item = normalize_emma_anchor(
                        source_name=source_name,
                        source_url=source_url,
                        text=anchor.get("text") or "",
                        href=anchor.get("href") or "",
                        keywords=keywords,
                    )
                    if item:
                        results.append(item)

                if results:
                    return results

                if any(keyword.lower() in page_text.lower() for keyword in keywords):
                    return [
                        self.manual_review_result(
                            source_name,
                            source_url,
                            "eMMA page contained configured keywords, but no public solicitation links matched the extractor.",
                        )
                    ]

                return [
                    self.manual_review_result(
                        source_name,
                        source_url,
                        "No public solicitation links matched configured keywords.",
                    )
                ]
            except Exception as exc:
                return [
                    self.manual_review_result(
                        source_name,
                        source_url,
                        f"eMMA scrape failed gracefully: {str(exc)[:200]}",
                    )
                ]
            finally:
                if context is not None:
                    context.close()
                if browser is not None:
                    browser.close()
