from __future__ import annotations

from app.models.source import Source
from app.services.source_service import load_seed_sources, sync_missing_seed_sources

MARYLAND_COUNTY_NAMES = {
    "Allegany County",
    "Anne Arundel County",
    "Baltimore County",
    "Calvert County",
    "Caroline County",
    "Carroll County",
    "Cecil County",
    "Charles County",
    "Dorchester County",
    "Frederick County",
    "Garrett County",
    "Harford County",
    "Howard County",
    "Kent County",
    "Montgomery County",
    "Prince George's County",
    "Queen Anne's County",
    "St. Mary's County",
    "Somerset County",
    "Talbot County",
    "Washington County",
    "Wicomico County",
    "Worcester County",
}


def test_sync_missing_seed_sources_inserts_missing_without_overwriting_existing(db_session):
    existing = Source(
        name="Howard County Procurement",
        url="https://custom.example.com/howard",
        source_type="generic",
        active=False,
        search_delay_seconds=9.0,
        notes="User edited",
    )
    db_session.add(existing)
    db_session.commit()

    created = sync_missing_seed_sources(db_session)
    db_session.refresh(existing)

    assert created > 0
    assert existing.url == "https://custom.example.com/howard"
    assert existing.active is False
    assert existing.search_delay_seconds == 9.0
    assert existing.notes == "User edited"
    assert db_session.query(Source).filter(Source.name == "Allegany County Bid Postings").count() == 1


def test_sync_missing_seed_sources_is_idempotent(db_session):
    first = sync_missing_seed_sources(db_session)
    second = sync_missing_seed_sources(db_session)

    assert first > 0
    assert second == 0
    assert db_session.query(Source).count() == len(load_seed_sources())


def test_seed_source_pack_includes_all_maryland_counties_and_baltimore_city():
    names = {source["name"] for source in load_seed_sources()}

    for county_name in MARYLAND_COUNTY_NAMES:
        assert any(county_name in source_name for source_name in names), county_name
    assert "Baltimore City Bid Opportunities" in names
