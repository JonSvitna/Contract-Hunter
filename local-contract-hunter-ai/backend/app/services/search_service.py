from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.opportunity import Opportunity
from app.models.source import Source
from app.scrapers.emma_scraper import EmmaScraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper
from app.services.score_persistence import score_and_store_opportunity
from app.services.source_service import (
    get_effective_throttle_for_source,
    load_business_profile,
    load_keywords,
)


@dataclass(frozen=True)
class SearchRunOptions:
    source_type: str | None = None
    source_name: str | None = None
    allow_mock_fallback: bool = True
    auto_score: bool = False


def mock_candidates(source_name: str, source_url: str) -> list[dict]:
    return [
        {
            "title": "Cybersecurity Vulnerability Assessment Services",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": "Local cybersecurity assessment and policy review support for municipal IT.",
            "extraction_confidence": 0.5,
            "manual_review_needed": True,
        },
        {
            "title": "NIST Gap Analysis and Security Awareness Training",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": "Short-term advisory engagement suitable for a solo consultant.",
            "extraction_confidence": 0.45,
            "manual_review_needed": True,
        },
    ]


def get_scraper_for_source(source: Source):
    throttle = get_effective_throttle_for_source(source.name)
    kwargs = {
        "delay_seconds": source.search_delay_seconds,
        "max_candidate_links": int(throttle.get("max_candidate_links", 120)),
        "page_timeout_ms": int(throttle.get("page_timeout_ms", 20000)),
        "body_timeout_ms": int(throttle.get("body_timeout_ms", 5000)),
    }
    if source.source_type.lower() == "emma":
        return EmmaScraper(**kwargs, browser_channel=settings.playwright_browser_channel)
    return GenericProcurementScraper(**kwargs)


def _query_sources(db: Session, options: SearchRunOptions) -> list[Source]:
    query = db.query(Source).filter(Source.active.is_(True))
    if options.source_type:
        query = query.filter(Source.source_type.ilike(options.source_type))
    if options.source_name:
        query = query.filter(Source.name == options.source_name)
    return query.all()


def _is_duplicate(db: Session, item: dict) -> bool:
    return (
        db.query(Opportunity)
        .filter(
            or_(
                Opportunity.opportunity_url == item.get("opportunity_url"),
                and_(
                    Opportunity.title == item.get("title"),
                    Opportunity.agency == item.get("agency"),
                    Opportunity.due_date == item.get("due_date"),
                ),
            )
        )
        .first()
        is not None
    )


def _create_opportunity(db: Session, source: Source, item: dict) -> Opportunity:
    row = Opportunity(
        title=item.get("title") or f"Opportunity from {source.name}",
        agency=item.get("agency") or source.name,
        source_name=source.name,
        source_url=source.url,
        opportunity_url=item.get("opportunity_url"),
        due_date=item.get("due_date"),
        description_snippet=item.get("description_snippet"),
        extraction_confidence=item.get("extraction_confidence", 0.4),
        manual_review_needed=item.get("manual_review_needed", False),
        status="Saved",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def execute_search(db: Session, options: SearchRunOptions | None = None) -> dict:
    options = options or SearchRunOptions()
    profile = load_business_profile()
    keywords = load_keywords()
    sources = _query_sources(db, options)
    created = 0
    skipped = 0
    scored = 0
    mock_fallback_used = False
    diagnostics: list[dict] = []

    for source in sources:
        scraper = get_scraper_for_source(source)
        candidates = scraper.scrape(source.name, source.url, keywords)
        diagnostics.append(
            {
                "source": source.name,
                "source_type": source.source_type,
                "candidates": len(candidates),
            }
        )

        for item in candidates:
            if _is_duplicate(db, item):
                skipped += 1
                continue
            row = _create_opportunity(db, source, item)
            created += 1
            if options.auto_score:
                score_and_store_opportunity(db, row, profile)
                scored += 1

    if created == 0 and sources and options.allow_mock_fallback:
        fallback_source = sources[0]
        mock_fallback_used = True
        for item in mock_candidates(fallback_source.name, fallback_source.url):
            if _is_duplicate(db, item):
                continue
            row = _create_opportunity(db, fallback_source, item)
            created += 1
            if options.auto_score:
                score_and_store_opportunity(db, row, profile)
                scored += 1

    return {
        "ok": True,
        "created": created,
        "duplicates_skipped": skipped,
        "sources": len(sources),
        "profile_name": profile.get("name", "Unknown"),
        "scored": scored,
        "mock_fallback_used": mock_fallback_used,
        "diagnostics": diagnostics,
    }
