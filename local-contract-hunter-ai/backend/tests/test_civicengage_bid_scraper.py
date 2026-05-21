from __future__ import annotations

from app.scrapers import civicengage_bid_scraper
from app.scrapers.civicengage_bid_scraper import CivicEngageBidScraper


class FakeBodyLocator:
    def __init__(self, text: str):
        self.text = text

    def inner_text(self, timeout: int) -> str:
        return self.text


class FakePage:
    def __init__(self, anchors: list[dict], body_text: str = ""):
        self.anchors = anchors
        self.body_text = body_text

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        pass

    def locator(self, selector: str) -> FakeBodyLocator:
        assert selector == "body"
        return FakeBodyLocator(self.body_text)

    def eval_on_selector_all(self, selector: str, script: str, limit: int) -> list[dict]:
        assert selector == "a"
        return self.anchors[:limit]


class FakeContext:
    def __init__(self, page: FakePage, close_error: Exception | None = None):
        self.page = page
        self.close_error = close_error

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        if self.close_error:
            raise self.close_error


class FakeBrowser:
    def __init__(self, page: FakePage, context_close_error: Exception | None = None):
        self.page = page
        self.context_close_error = context_close_error

    def new_context(self) -> FakeContext:
        return FakeContext(self.page, close_error=self.context_close_error)

    def close(self) -> None:
        pass


class FakeChromium:
    def __init__(self, page: FakePage, context_close_error: Exception | None = None):
        self.page = page
        self.context_close_error = context_close_error

    def launch(self, headless: bool) -> FakeBrowser:
        assert headless is True
        return FakeBrowser(self.page, context_close_error=self.context_close_error)


class FakePlaywright:
    def __init__(self, chromium: FakeChromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def install_fake_playwright(
    monkeypatch,
    page: FakePage,
    context_close_error: Exception | None = None,
) -> None:
    chromium = FakeChromium(page=page, context_close_error=context_close_error)
    monkeypatch.setattr(civicengage_bid_scraper, "sync_playwright", lambda: FakePlaywright(chromium))


def test_bid_id_keyword_anchor_creates_non_manual_review_candidate(monkeypatch):
    page = FakePage(
        anchors=[
            {
                "href": "Bids.aspx?bidID=123",
                "text": "Cybersecurity Risk Assessment RFP Due Date: 12/31/2099",
            }
        ],
        body_text="Open bids",
    )
    install_fake_playwright(monkeypatch, page)

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Allegany County Bid Postings",
        "https://www.alleganygov.org/bids.aspx",
        ["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["manual_review_needed"] is False
    assert results[0]["opportunity_url"] == "https://www.alleganygov.org/Bids.aspx?bidID=123"
    assert results[0]["due_date"].isoformat() == "2099-12-31"
    assert results[0]["extraction_confidence"] >= 0.75


def test_non_keyword_bid_anchor_creates_specific_manual_review_candidate(monkeypatch):
    page = FakePage(
        anchors=[{"href": "Bids.aspx?bidID=456", "text": "Road salt supply bid"}],
        body_text="Open bids including cybersecurity consulting",
    )
    install_fake_playwright(monkeypatch, page)

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Caroline County Bid Opportunities",
        "https://www.carolinemd.org/Bids.aspx",
        ["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["manual_review_needed"] is True
    assert results[0]["opportunity_url"] == "https://www.carolinemd.org/Bids.aspx?bidID=456"
    assert results[0]["extraction_confidence"] >= 0.45


def test_duplicate_bid_links_are_emitted_once(monkeypatch):
    page = FakePage(
        anchors=[
            {"href": "Bids.aspx?bidID=456", "text": "Cybersecurity assessment"},
            {"href": "Bids.aspx?bidID=456", "text": "Cybersecurity assessment duplicate"},
        ],
        body_text="Open bids",
    )
    install_fake_playwright(monkeypatch, page)

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Queen Anne's County Bid Postings",
        "https://www.qac.org/bids.aspx",
        ["cybersecurity"],
    )

    assert len(results) == 1


def test_navigation_links_on_bid_page_are_ignored(monkeypatch):
    page = FakePage(
        anchors=[
            {
                "href": "Bids.aspx?CatID=All&Status=&showAllBids=on&txtSort=Category",
                "text": "Bid Opportunities",
            },
            {
                "href": "Bids.aspx?CatID=All&Status=&showAllBids=on&txtSort=Category#contentarea",
                "text": "Skip to Main Content",
            },
            {
                "href": "list.aspx?Mode=Subscribe#bids",
                "text": "Sign up",
            },
            {
                "href": "bids.aspx?bidID=302",
                "text": "Arc Flash Analysis and Electric Panel Labeling Study",
            },
        ],
        body_text="Open bids",
    )
    install_fake_playwright(monkeypatch, page)

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Wicomico County Bid Postings",
        "https://www.wicomicocounty.org/Bids.aspx?CatID=All&Status=&showAllBids=on&txtSort=Category",
        ["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["title"] == "Arc Flash Analysis and Electric Panel Labeling Study"
    assert results[0]["opportunity_url"] == "https://www.wicomicocounty.org/bids.aspx?bidID=302"


def test_no_bid_links_returns_manual_review_fallback(monkeypatch):
    page = FakePage(
        anchors=[{"href": "departments/purchasing", "text": "Purchasing office"}],
        body_text="Vendor registration and purchasing rules",
    )
    install_fake_playwright(monkeypatch, page)

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Wicomico County Bid Postings",
        "https://www.wicomicocounty.org/Bids.aspx",
        ["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["title"] == "Manual review needed for Wicomico County Bid Postings"
    assert results[0]["manual_review_needed"] is True


def test_cleanup_failure_does_not_escape(monkeypatch):
    page = FakePage(
        anchors=[{"href": "Bids.aspx?bidID=789", "text": "Cybersecurity assessment"}],
        body_text="Open bids",
    )
    install_fake_playwright(
        monkeypatch,
        page,
        context_close_error=RuntimeError("Event loop is closed! Is Playwright already stopped?"),
    )

    results = CivicEngageBidScraper(delay_seconds=0).scrape(
        "Allegany County Bid Postings",
        "https://www.alleganygov.org/bids.aspx",
        ["cybersecurity"],
    )

    assert len(results) == 1
