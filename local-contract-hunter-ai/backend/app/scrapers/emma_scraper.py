from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

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

PUBLIC_SOLICITATIONS_PATH = "/page.aspx/en/rfp/request_browse_public"
SEARCH_INPUT_SELECTORS = [
    'input[aria-label*="keyword" i]',
    'input[placeholder*="keyword" i]',
    'input[id*="keyword" i]',
    'input[name*="keyword" i]',
    'textarea[aria-label*="keyword" i]',
    'textarea[placeholder*="keyword" i]',
]
SEARCH_BUTTON_SELECTORS = [
    'button:has-text("Search")',
    'input[type="submit"][value*="Search" i]',
    'input[type="button"][value*="Search" i]',
]


def public_solicitations_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc or 'emma.maryland.gov'}"
    return urljoin(base, PUBLIC_SOLICITATIONS_PATH)


def _looks_like_emma_opportunity(text: str, href: str, keywords: list[str]) -> bool:
    lowered_text = text.lower()
    lowered_href = href.lower()
    if any(nav in lowered_text for nav in ["login", "register", "help", "training", "contact"]):
        return False
    has_emma_pattern = any(pattern in lowered_href or pattern in lowered_text for pattern in EMMA_SOLICITATION_PATTERNS)
    has_keyword = any(keyword.lower() in lowered_text for keyword in keywords)
    return has_emma_pattern and has_keyword


def _agency_from_text(text: str, source_name: str) -> str:
    match = re.search(
        r"(Maryland [A-Za-z0-9&.,' -]+?)(?: Due Date:| Closing Date:| Due:|$)",
        text,
    )
    if match:
        return match.group(1).strip()
    return source_name


def normalize_emma_result(
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


def normalize_emma_anchor(
    source_name: str,
    source_url: str,
    text: str,
    href: str,
    keywords: list[str],
) -> dict | None:
    return normalize_emma_result(source_name, source_url, text, href, keywords)


class EmmaScraper(BaseScraper):
    def __init__(
        self,
        delay_seconds: float = 2.0,
        max_candidate_links: int = 120,
        page_timeout_ms: int = 20000,
        body_timeout_ms: int = 5000,
        browser_channel: str | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.max_candidate_links = max_candidate_links
        self.page_timeout_ms = page_timeout_ms
        self.body_timeout_ms = body_timeout_ms
        self.browser_channel = browser_channel

    def _launch_browser(self, playwright):
        launch_options = {"headless": True}
        if self.browser_channel:
            launch_options["channel"] = self.browser_channel
        return playwright.chromium.launch(**launch_options)

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

    def _wait_for_public_solicitations(self, page, source_name: str, source_url: str) -> dict | None:
        if "browser_check" not in page.url:
            return None

        try:
            public_link = page.locator('a:has-text("Public Solicitations")').first
            public_link.click(timeout=5000)
            page.wait_for_timeout(int(self.delay_seconds * 1000))
        except Exception:
            pass

        if "browser_check" in page.url:
            return self.manual_review_result(
                source_name,
                source_url,
                "eMMA Public Solicitations opened the browser-check page and did not complete in the automated browser.",
            )
        return None

    def _search_keyword(self, page, keyword: str) -> None:
        for selector in SEARCH_INPUT_SELECTORS:
            field = page.locator(selector).first
            try:
                if field.count() == 0 or not field.is_visible(timeout=1000):
                    continue
                field.fill(keyword, timeout=3000)
                for button_selector in SEARCH_BUTTON_SELECTORS:
                    button = page.locator(button_selector).first
                    try:
                        if button.count() > 0 and button.is_visible(timeout=1000):
                            button.click(timeout=3000)
                            page.wait_for_load_state("domcontentloaded", timeout=self.page_timeout_ms)
                            page.wait_for_timeout(int(self.delay_seconds * 1000))
                            return
                    except Exception:
                        continue
                field.press("Enter", timeout=3000)
                page.wait_for_timeout(int(self.delay_seconds * 1000))
                return
            except Exception:
                continue

    def _extract_results_from_page(self, page, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        results: list[dict] = []
        rows = page.eval_on_selector_all(
            "tr",
            """(elements, limit) => elements.slice(0, limit).map(row => {
                const link = row.querySelector('a');
                return {
                    href: link ? link.href || '' : '',
                    text: (row.innerText || row.textContent || '').trim()
                };
            })""",
            self.max_candidate_links,
        )

        for row in rows:
            item = normalize_emma_result(
                source_name=source_name,
                source_url=source_url,
                text=row.get("text") or "",
                href=row.get("href") or "",
                keywords=keywords,
            )
            if item:
                results.append(item)

        anchors = page.eval_on_selector_all(
            "a",
            "(elements, limit) => elements.slice(0, limit).map(e => ({href: e.href || '', text: (e.innerText || e.textContent || '').trim()}))",
            self.max_candidate_links,
        )

        seen_urls = {item.get("opportunity_url") for item in results}
        for anchor in anchors:
            item = normalize_emma_anchor(
                source_name=source_name,
                source_url=source_url,
                text=anchor.get("text") or "",
                href=anchor.get("href") or "",
                keywords=keywords,
            )
            if item and item.get("opportunity_url") not in seen_urls:
                seen_urls.add(item.get("opportunity_url"))
                results.append(item)

        return results

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
                browser = self._launch_browser(p)
                context = browser.new_context()
                page = context.new_page()
                target_url = public_solicitations_url(source_url)
                page.goto(target_url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
                time.sleep(self.delay_seconds)

                browser_check_result = self._wait_for_public_solicitations(page, source_name, source_url)
                if browser_check_result:
                    return [browser_check_result]

                for keyword in keywords:
                    self._search_keyword(page, keyword)
                    results.extend(self._extract_results_from_page(page, source_name, source_url, [keyword]))
                    if results:
                        return results

                page_text = page.locator("body").inner_text(timeout=self.body_timeout_ms)
                results.extend(self._extract_results_from_page(page, source_name, source_url, keywords))

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
