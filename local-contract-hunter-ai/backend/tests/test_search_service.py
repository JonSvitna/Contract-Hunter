from __future__ import annotations

from datetime import date

from app.models.opportunity import Opportunity
from app.models.source import Source
from app.models.source_run import SourceRun, SourceRunItem
from app.scrapers.civicengage_bid_scraper import CivicEngageBidScraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper
from app.services import search_service
from app.services.search_service import SearchRunOptions, execute_search, get_scraper_for_source


class FakeScraper:
    def __init__(self, candidates):
        self.candidates = candidates

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        return self.candidates


def test_get_scraper_for_source_uses_civicengage_for_bids_aspx_source():
    source = Source(
        name="Allegany County Bid Postings",
        url="https://www.alleganygov.org/bids.aspx",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )

    scraper = get_scraper_for_source(source)

    assert isinstance(scraper, CivicEngageBidScraper)


def test_get_scraper_for_source_uses_generic_for_regular_generic_source():
    source = Source(
        name="Howard County Procurement",
        url="https://www.howardcountymd.gov/procurement",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )

    scraper = get_scraper_for_source(source)

    assert isinstance(scraper, GenericProcurementScraper)


def test_execute_search_filters_to_emma_and_scores_new_rows(db_session, monkeypatch):
    emma = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    county = Source(
        name="County Source",
        url="https://example.com/county",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add_all([emma, county])
    db_session.commit()

    candidates = [
        {
            "title": "Cybersecurity Risk Assessment",
            "agency": "Maryland Department of Test",
            "source_name": "Maryland eMMA",
            "source_url": "https://emma.maryland.gov/",
            "opportunity_url": "https://emma.maryland.gov/opportunity/1",
            "due_date": date(2099, 1, 15),
            "description_snippet": "NIST cybersecurity risk assessment and policy review.",
            "extraction_confidence": 0.9,
            "manual_review_needed": False,
        }
    ]

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity", "NIST"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper(candidates))

    result = execute_search(
        db_session,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )

    rows = db_session.query(Opportunity).all()
    assert result["ok"] is True
    assert result["sources"] == 1
    assert result["created"] == 1
    assert result["scored"] == 1
    assert result["mock_fallback_used"] is False
    assert rows[0].source_name == "Maryland eMMA"
    assert rows[0].score is not None


def test_execute_search_skips_duplicates_on_second_run(db_session, monkeypatch):
    source = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    candidates = [
        {
            "title": "Cybersecurity Risk Assessment",
            "agency": "Maryland Department of Test",
            "source_name": "Maryland eMMA",
            "source_url": "https://emma.maryland.gov/",
            "opportunity_url": "https://emma.maryland.gov/opportunity/1",
            "due_date": date(2099, 1, 15),
            "description_snippet": "NIST cybersecurity risk assessment and policy review.",
            "extraction_confidence": 0.9,
            "manual_review_needed": False,
        }
    ]

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity", "NIST"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper(candidates))

    first = execute_search(db_session, SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True))
    second = execute_search(db_session, SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True))

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["duplicates_skipped"] == 1
    assert db_session.query(Opportunity).count() == 1


def test_execute_search_validation_does_not_insert_mock_fallback(db_session, monkeypatch):
    source = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper([]))

    result = execute_search(
        db_session,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )

    assert result["created"] == 0
    assert result["mock_fallback_used"] is False
    assert db_session.query(Opportunity).count() == 0


def test_execute_search_filters_by_generic_source_name_scores_and_skips_duplicates(db_session, monkeypatch):
    target = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    other = Source(
        name="Baltimore County Procurement",
        url="https://example.com/baltimore",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add_all([target, other])
    db_session.commit()

    candidates_by_source = {
        "Howard County Procurement": [
            {
                "title": "Cybersecurity Assessment",
                "agency": "Howard County Procurement",
                "source_name": "Howard County Procurement",
                "source_url": "https://example.com/howard",
                "opportunity_url": "https://example.com/howard/bids/1",
                "due_date": date(2099, 1, 15),
                "description_snippet": "County cybersecurity risk assessment and NIST policy review.",
                "extraction_confidence": 0.9,
                "manual_review_needed": False,
            }
        ],
        "Baltimore County Procurement": [
            {
                "title": "Should Not Be Scraped",
                "agency": "Baltimore County Procurement",
                "source_name": "Baltimore County Procurement",
                "source_url": "https://example.com/baltimore",
                "opportunity_url": "https://example.com/baltimore/bids/1",
                "due_date": date(2099, 1, 15),
                "description_snippet": "This source should not run.",
                "extraction_confidence": 0.9,
                "manual_review_needed": False,
            }
        ],
    }
    scraped_sources: list[str] = []

    def fake_scraper_for_source(source):
        scraped_sources.append(source.name)
        return FakeScraper(candidates_by_source[source.name])

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity", "NIST"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", fake_scraper_for_source)

    options = SearchRunOptions(
        source_name="Howard County Procurement",
        allow_mock_fallback=False,
        auto_score=True,
    )
    first = execute_search(db_session, options)
    second = execute_search(db_session, options)

    rows = db_session.query(Opportunity).all()
    assert scraped_sources == ["Howard County Procurement", "Howard County Procurement"]
    assert first["sources"] == 1
    assert first["created"] == 1
    assert first["scored"] == 1
    assert first["mock_fallback_used"] is False
    assert second["created"] == 0
    assert second["duplicates_skipped"] == 1
    assert second["mock_fallback_used"] is False
    assert len(rows) == 1
    assert rows[0].source_name == "Howard County Procurement"
    assert rows[0].score is not None


def test_execute_search_persists_source_run_items_and_duplicate_history(db_session, monkeypatch):
    source = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    candidates = [
        {
            "title": "Manual Review Cyber Assessment",
            "agency": "Howard County Procurement",
            "source_name": "Howard County Procurement",
            "source_url": "https://example.com/howard",
            "opportunity_url": "https://example.com/howard/bids/manual",
            "due_date": date(2099, 1, 15),
            "description_snippet": "County cybersecurity work that needs manual review.",
            "extraction_confidence": 0.42,
            "manual_review_needed": True,
        }
    ]

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper(candidates))

    first = execute_search(
        db_session,
        SearchRunOptions(
            source_name="Howard County Procurement",
            allow_mock_fallback=False,
            auto_score=True,
            run_kind="validation",
        ),
    )
    second = execute_search(
        db_session,
        SearchRunOptions(
            source_name="Howard County Procurement",
            allow_mock_fallback=False,
            auto_score=True,
            run_kind="validation",
        ),
    )

    runs = db_session.query(SourceRun).order_by(SourceRun.id.asc()).all()
    items = db_session.query(SourceRunItem).order_by(SourceRunItem.id.asc()).all()

    assert first["source_run_id"] == runs[0].id
    assert first["diagnostics"][0]["source_run_id"] == runs[0].id
    assert first["diagnostics"][0]["manual_review_candidates"] == 1
    assert runs[0].status == "completed"
    assert runs[0].run_kind == "validation"
    assert runs[0].candidates_found == 1
    assert runs[0].created == 1
    assert runs[0].duplicates_skipped == 0
    assert runs[0].scored == 1
    assert runs[0].manual_review_candidates == 1
    assert runs[0].manual_review_created == 1
    assert runs[0].finished_at is not None
    assert runs[0].duration_ms is not None
    assert second["duplicates_skipped"] == 1
    assert runs[1].created == 0
    assert runs[1].duplicates_skipped == 1
    assert [item.action for item in items] == ["scored", "duplicate"]
    assert items[0].opportunity_id is not None
    assert items[0].manual_review_needed is True


def test_execute_search_records_failed_source_run_and_continues(db_session, monkeypatch):
    broken = Source(
        name="Broken County",
        url="https://example.com/broken",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    working = Source(
        name="Working County",
        url="https://example.com/working",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add_all([broken, working])
    db_session.commit()

    class RaisingScraper:
        def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
            raise RuntimeError("browser crashed with a very noisy traceback")

    candidates = [
        {
            "title": "Cybersecurity Assessment",
            "agency": "Working County",
            "source_name": "Working County",
            "source_url": "https://example.com/working",
            "opportunity_url": "https://example.com/working/bids/1",
            "due_date": date(2099, 1, 15),
            "description_snippet": "County cybersecurity assessment.",
            "extraction_confidence": 0.9,
            "manual_review_needed": False,
        }
    ]

    def fake_scraper_for_source(source):
        if source.name == "Broken County":
            return RaisingScraper()
        return FakeScraper(candidates)

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", fake_scraper_for_source)

    result = execute_search(db_session, SearchRunOptions(allow_mock_fallback=False))
    runs = db_session.query(SourceRun).order_by(SourceRun.source_name.asc()).all()

    assert result["created"] == 1
    assert result["sources"] == 2
    assert {run.source_name: run.status for run in runs} == {
        "Broken County": "failed",
        "Working County": "completed",
    }
    assert "browser crashed" in runs[0].error_message
    assert runs[1].created == 1
