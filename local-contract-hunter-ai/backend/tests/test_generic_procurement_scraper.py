from __future__ import annotations

from app.scrapers import generic_procurement_scraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper


class FakeBodyLocator:
    def __init__(self, text: str):
        self.text = text

    def inner_text(self, timeout: int) -> str:
        return self.text


class FakePage:
    def __init__(self, anchors: list[dict], body_text: str = ""):
        self.anchors = anchors
        self.body_text = body_text
        self.goto_calls: list[dict] = []

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})

    def locator(self, selector: str) -> FakeBodyLocator:
        assert selector == "body"
        return FakeBodyLocator(self.body_text)

    def eval_on_selector_all(self, selector: str, script: str, limit: int) -> list[dict]:
        assert selector == "a"
        assert "elements.slice" in script
        return self.anchors[:limit]


class FakeContext:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False

    def new_context(self) -> FakeContext:
        return FakeContext(self.page)

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, page: FakePage | None = None, launch_error: Exception | None = None):
        self.page = page or FakePage([])
        self.launch_error = launch_error

    def launch(self, headless: bool) -> FakeBrowser:
        assert headless is True
        if self.launch_error:
            raise self.launch_error
        return FakeBrowser(self.page)


class FakePlaywright:
    def __init__(self, chromium: FakeChromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def install_fake_playwright(monkeypatch, page: FakePage | None = None, launch_error: Exception | None = None) -> None:
    chromium = FakeChromium(page=page, launch_error=launch_error)
    monkeypatch.setattr(generic_procurement_scraper, "sync_playwright", lambda: FakePlaywright(chromium))


def test_keyword_matching_anchor_creates_candidate_with_joined_relative_url(monkeypatch):
    page = FakePage(
        anchors=[
            {
                "href": "bids/cyber-risk-assessment",
                "text": "Cybersecurity Risk Assessment Due Date: 12/31/2099",
            }
        ],
        body_text="Procurement opportunities",
    )
    install_fake_playwright(monkeypatch, page=page)

    results = GenericProcurementScraper(delay_seconds=0).scrape(
        source_name="Baltimore County Procurement",
        source_url="https://example.test/procurement/",
        keywords=["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["manual_review_needed"] is False
    assert results[0]["title"] == "Cybersecurity Risk Assessment Due Date: 12/31/2099"
    assert results[0]["opportunity_url"] == "https://example.test/procurement/bids/cyber-risk-assessment"
    assert results[0]["due_date"].isoformat() == "2099-12-31"


def test_no_keyword_match_returns_manual_review_fallback(monkeypatch):
    page = FakePage(
        anchors=[{"href": "bids/road-salt", "text": "Road salt supply bid"}],
        body_text="General purchasing notices and vendor registration",
    )
    install_fake_playwright(monkeypatch, page=page)

    results = GenericProcurementScraper(delay_seconds=0).scrape(
        source_name="Howard County Procurement",
        source_url="https://example.test/procurement/",
        keywords=["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["title"] == "Manual review needed for Howard County Procurement"
    assert results[0]["manual_review_needed"] is True
    assert results[0]["opportunity_url"] == "https://example.test/procurement/"


def test_browser_failure_returns_manual_review_failure_candidate(monkeypatch):
    install_fake_playwright(monkeypatch, launch_error=RuntimeError("browser failed to launch"))

    results = GenericProcurementScraper(delay_seconds=0).scrape(
        source_name="Anne Arundel County Purchasing",
        source_url="https://example.test/purchasing/",
        keywords=["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["title"] == "Manual review needed for Anne Arundel County Purchasing"
    assert results[0]["manual_review_needed"] is True
    assert "Scrape failed gracefully" in results[0]["description_snippet"]
    assert "browser failed to launch" in results[0]["description_snippet"]
