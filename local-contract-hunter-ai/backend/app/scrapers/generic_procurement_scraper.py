from __future__ import annotations

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


class GenericProcurementScraper(BaseScraper):
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
            return [
                {
                    "title": f"Manual review needed for {source_name}",
                    "agency": source_name,
                    "source_name": source_name,
                    "source_url": source_url,
                    "opportunity_url": source_url,
                    "due_date": None,
                    "description_snippet": "Playwright not installed locally. Source retained for manual review.",
                    "extraction_confidence": 0.2,
                    "manual_review_needed": True,
                }
            ]

        results: list[dict] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
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
                    if not any(k.lower() in text.lower() for k in keywords):
                        continue

                    joined = urljoin(source_url, href)
                    due_date = parse_possible_due_date(text)
                    snippet = snippet_with_keywords(text, keywords)
                    results.append(
                        {
                            "title": text[:500],
                            "agency": source_name,
                            "source_name": source_name,
                            "source_url": source_url,
                            "opportunity_url": joined,
                            "due_date": due_date,
                            "description_snippet": snippet,
                            "extraction_confidence": confidence_from_text(text, keywords),
                            "manual_review_needed": False,
                        }
                    )

                if not results:
                    # If keyword links were not obvious, retain a manual review item.
                    results.append(
                        {
                            "title": f"Manual review needed for {source_name}",
                            "agency": source_name,
                            "source_name": source_name,
                            "source_url": source_url,
                            "opportunity_url": source_url,
                            "due_date": parse_possible_due_date(body_text),
                            "description_snippet": snippet_with_keywords(body_text, keywords),
                            "extraction_confidence": confidence_from_text(body_text, keywords),
                            "manual_review_needed": True,
                        }
                    )
            except Exception as exc:
                results = [
                    {
                        "title": f"Manual review needed for {source_name}",
                        "agency": source_name,
                        "source_name": source_name,
                        "source_url": source_url,
                        "opportunity_url": source_url,
                        "due_date": None,
                        "description_snippet": f"Scrape failed gracefully: {str(exc)[:200]}",
                        "extraction_confidence": 0.2,
                        "manual_review_needed": True,
                    }
                ]
            finally:
                context.close()
                browser.close()
        return results
