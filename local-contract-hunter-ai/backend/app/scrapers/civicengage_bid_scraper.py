from __future__ import annotations

import time
from contextlib import suppress
from urllib.parse import urldefrag, urljoin, urlparse

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


BID_TERMS = ("bid", "rfp", "proposal", "solicitation", "quote")


class CivicEngageBidScraper(BaseScraper):
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

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        if sync_playwright is None:
            return [self._failure_candidate(source_name, source_url, "Playwright not installed locally.")]

        results: list[dict] = []
        seen_urls: set[str] = set()
        browser = None
        context = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto(source_url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
                time.sleep(self.delay_seconds)
                body_text = page.locator("body").inner_text(timeout=self.body_timeout_ms)
                anchors = page.eval_on_selector_all(
                    "a",
                    "(elements, limit) => elements.slice(0, limit).map(e => ({href: e.href || '', text: (e.innerText || '').trim()}))",
                    self.max_candidate_links,
                )

                for anchor in anchors:
                    text = (anchor.get("text") or "").strip()
                    href = anchor.get("href") or ""
                    if not text or not href:
                        continue
                    joined = urljoin(source_url, href)
                    if joined in seen_urls or not self._looks_like_bid_link(text, joined, source_url):
                        continue
                    seen_urls.add(joined)
                    combined_text = f"{text} {body_text}"
                    keyword_match = any(keyword.lower() in text.lower() for keyword in keywords)
                    due_date = parse_possible_due_date(text) or parse_possible_due_date(body_text)
                    confidence = confidence_from_text(text, keywords)
                    confidence = max(confidence, 0.75 if keyword_match else 0.45)
                    results.append(
                        {
                            "title": text[:500],
                            "agency": source_name,
                            "source_name": source_name,
                            "source_url": source_url,
                            "opportunity_url": joined,
                            "due_date": due_date,
                            "description_snippet": snippet_with_keywords(combined_text, keywords),
                            "extraction_confidence": min(confidence, 1.0),
                            "manual_review_needed": not keyword_match,
                        }
                    )

                if not results:
                    results.append(
                        {
                            "title": f"Manual review needed for {source_name}",
                            "agency": source_name,
                            "source_name": source_name,
                            "source_url": source_url,
                            "opportunity_url": source_url,
                            "due_date": parse_possible_due_date(body_text),
                            "description_snippet": snippet_with_keywords(body_text, keywords),
                            "extraction_confidence": 0.2,
                            "manual_review_needed": True,
                        }
                    )
        except Exception as exc:
            results = [self._failure_candidate(source_name, source_url, f"Scrape failed gracefully: {str(exc)[:200]}")]
        finally:
            if context is not None:
                with suppress(Exception):
                    context.close()
            if browser is not None:
                with suppress(Exception):
                    browser.close()
        return results

    @staticmethod
    def _looks_like_bid_link(text: str, url: str, source_url: str) -> bool:
        parsed = urlparse(urldefrag(url).url)
        if "bidid=" in parsed.query.lower():
            return True
        source_path = urlparse(source_url).path.lower()
        if parsed.path.lower() == source_path and "bids.aspx" in source_path:
            return False
        return any(term in text.lower() for term in BID_TERMS)

    @staticmethod
    def _failure_candidate(source_name: str, source_url: str, message: str) -> dict:
        return {
            "title": f"Manual review needed for {source_name}",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": message,
            "extraction_confidence": 0.2,
            "manual_review_needed": True,
        }
