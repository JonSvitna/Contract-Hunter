from __future__ import annotations

from app.scrapers.emma_scraper import EmmaScraper, normalize_emma_anchor


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
