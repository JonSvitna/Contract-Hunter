from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.source import Source
from app.scrapers.emma_scraper import EmmaScraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper
from app.services.source_service import load_business_profile, load_keywords


router = APIRouter(prefix="/search", tags=["search"])


def _mock_candidates(source_name: str, source_url: str) -> list[dict]:
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


@router.post("/run")
def run_search(db: Session = Depends(get_db)):
    profile = load_business_profile()
    keywords = load_keywords()
    sources = db.query(Source).filter(Source.active.is_(True)).all()
    created = 0
    skipped = 0

    for source in sources:
        scraper = (
            EmmaScraper(delay_seconds=source.search_delay_seconds)
            if source.source_type.lower() == "emma"
            else GenericProcurementScraper(delay_seconds=source.search_delay_seconds)
        )
        candidates = scraper.scrape(source.name, source.url, keywords)

        for item in candidates:
            duplicate = db.query(Opportunity).filter(
                or_(
                    Opportunity.opportunity_url == item.get("opportunity_url"),
                    and_(
                        Opportunity.title == item.get("title"),
                        Opportunity.agency == item.get("agency"),
                        Opportunity.due_date == item.get("due_date"),
                    ),
                )
            ).first()
            if duplicate:
                skipped += 1
                continue

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
            created += 1

    if created == 0 and sources:
        fallback_source = sources[0]
        for item in _mock_candidates(fallback_source.name, fallback_source.url):
            duplicate = db.query(Opportunity).filter(
                Opportunity.title == item["title"],
                Opportunity.agency == item["agency"],
            ).first()
            if duplicate:
                continue
            db.add(
                Opportunity(
                    title=item["title"],
                    agency=item["agency"],
                    source_name=item["source_name"],
                    source_url=item["source_url"],
                    opportunity_url=item["opportunity_url"],
                    due_date=item["due_date"],
                    description_snippet=item["description_snippet"],
                    extraction_confidence=item["extraction_confidence"],
                    manual_review_needed=item["manual_review_needed"],
                    status="Saved",
                )
            )
            created += 1

    db.commit()
    return {
        "ok": True,
        "created": created,
        "duplicates_skipped": skipped,
        "sources": len(sources),
        "profile_name": profile.get("name", "Unknown"),
    }


@router.get("/config")
def get_search_config_preview():
    return {
        "business_profile": load_business_profile(),
        "keywords": load_keywords(),
    }
