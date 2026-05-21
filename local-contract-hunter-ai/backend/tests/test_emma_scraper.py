from __future__ import annotations

from app.scrapers import emma_scraper
from app.scrapers.emma_scraper import (
    EmmaScraper,
    public_solicitations_url,
    normalize_emma_anchor,
    normalize_emma_result,
)


def test_normalize_emma_anchor_accepts_solicitation_link():
    item = normalize_emma_anchor(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text="BPM046789 Cybersecurity Risk Assessment Maryland Department of Test Due Date: 12/31/2099",
        href="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/46789",
        keywords=["cybersecurity", "risk assessment"],
    )

    assert item is not None
    assert item["title"].startswith("BPM046789 Cybersecurity Risk Assessment")
    assert item["agency"] == "Maryland Department of Test"
    assert item["opportunity_url"].endswith("/46789")
    assert item["due_date"].isoformat() == "2099-12-31"
    assert item["extraction_confidence"] >= 0.75
    assert item["manual_review_needed"] is False


def test_normalize_emma_anchor_rejects_navigation_link():
    item = normalize_emma_anchor(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text="Login",
        href="https://emma.maryland.gov/page.aspx/en/usr/login",
        keywords=["cybersecurity"],
    )

    assert item is None


def test_public_solicitations_url_uses_emma_base():
    assert public_solicitations_url("https://emma.maryland.gov/") == (
        "https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public"
    )


def test_normalize_emma_result_accepts_public_solicitation_row():
    item = normalize_emma_result(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text=(
            "BPM056061 Cybersecurity Risk Assessment for Information Security "
            "Maryland Judiciary Closing Date: 04/13/2026 02:00 PM"
        ),
        href="/page.aspx/en/bpm/process_manage_extranet/56061",
        keywords=["cybersecurity", "risk assessment"],
    )

    assert item is not None
    assert item["title"].startswith("BPM056061 Cybersecurity Risk Assessment")
    assert item["agency"] == "Maryland Judiciary"
    assert item["opportunity_url"] == "https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/56061"
    assert item["due_date"].isoformat() == "2026-04-13"
    assert item["extraction_confidence"] >= 0.75
    assert item["manual_review_needed"] is False


def test_normalize_emma_result_rejects_rows_without_keywords():
    item = normalize_emma_result(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text="BPM000001 Road Salt Supplies Maryland Department of Test Closing Date: 04/13/2026",
        href="/page.aspx/en/bpm/process_manage_extranet/1",
        keywords=["cybersecurity"],
    )

    assert item is None


def test_manual_review_result_names_emma_failure():
    scraper = EmmaScraper()
    item = scraper.manual_review_result(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        reason="No public solicitation links matched configured keywords.",
    )

    assert item["title"] == "Manual review needed for Maryland eMMA"
    assert item["manual_review_needed"] is True
    assert item["extraction_confidence"] == 0.2
    assert "No public solicitation links" in item["description_snippet"]


def test_scrape_returns_manual_review_when_browser_launch_fails(monkeypatch):
    class FakeChromium:
        def launch(self, headless: bool):
            raise RuntimeError("browser failed to launch")

    class FakePlaywright:
        chromium = FakeChromium()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(emma_scraper, "sync_playwright", lambda: FakePlaywright())

    results = EmmaScraper().scrape(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        keywords=["cybersecurity"],
    )

    assert len(results) == 1
    assert results[0]["manual_review_needed"] is True
    assert "eMMA scrape failed gracefully" in results[0]["description_snippet"]
