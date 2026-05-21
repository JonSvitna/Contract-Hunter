from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.opportunity import Opportunity
from app.models.source import Source
from app.models.source_run import SourceRun, SourceRunItem
from app.scrapers.civicengage_bid_scraper import CivicEngageBidScraper
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
    run_kind: str = "manual"
    persist_run_history: bool = True


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
    if _is_civicengage_bid_source(source):
        return CivicEngageBidScraper(**kwargs)
    return GenericProcurementScraper(**kwargs)


def _is_civicengage_bid_source(source: Source) -> bool:
    path = urlparse(source.url).path.lower()
    return "bids.aspx" in path


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


def _safe_error_message(exc: Exception) -> str:
    return str(exc).splitlines()[0][:500] or exc.__class__.__name__


def _start_source_run(db: Session, source: Source, options: SearchRunOptions) -> SourceRun | None:
    if not options.persist_run_history:
        return None
    run = SourceRun(
        source_id=source.id,
        source_name=source.name,
        source_type=source.source_type,
        source_url=source.url,
        run_kind=options.run_kind,
        status="running",
        auto_score=options.auto_score,
        mock_fallback_allowed=options.allow_mock_fallback,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_source_run(db: Session, run: SourceRun | None, status: str, error_message: str | None = None) -> None:
    if not run:
        return
    finished_at = datetime.utcnow()
    run.status = status
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - run.started_at).total_seconds() * 1000)
    run.error_message = error_message
    db.commit()


def _record_source_run_item(
    db: Session,
    run: SourceRun | None,
    item: dict,
    action: str,
    opportunity_id: int | None = None,
    error_message: str | None = None,
) -> None:
    if not run:
        return
    db.add(
        SourceRunItem(
            source_run_id=run.id,
            opportunity_id=opportunity_id,
            action=action,
            title=item.get("title"),
            agency=item.get("agency"),
            opportunity_url=item.get("opportunity_url"),
            due_date=item.get("due_date"),
            extraction_confidence=item.get("extraction_confidence"),
            manual_review_needed=bool(item.get("manual_review_needed", False)),
            error_message=error_message,
        )
    )


def _apply_run_counts(
    run: SourceRun | None,
    *,
    candidates_found: int,
    created: int,
    duplicates_skipped: int,
    scored: int,
    manual_review_candidates: int,
    manual_review_created: int,
) -> None:
    if not run:
        return
    run.candidates_found += candidates_found
    run.created += created
    run.duplicates_skipped += duplicates_skipped
    run.scored += scored
    run.manual_review_candidates += manual_review_candidates
    run.manual_review_created += manual_review_created


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
    source_runs: list[tuple[Source, SourceRun | None]] = []

    for source in sources:
        run = _start_source_run(db, source, options)
        source_runs.append((source, run))
        source_created = 0
        source_skipped = 0
        source_scored = 0
        source_manual_review_created = 0
        source_manual_review_candidates = 0
        candidates: list[dict] = []

        try:
            scraper = get_scraper_for_source(source)
            candidates = scraper.scrape(source.name, source.url, keywords)
            source_manual_review_candidates = sum(
                1 for item in candidates if item.get("manual_review_needed", False)
            )
            diagnostics.append(
                {
                    "source": source.name,
                    "source_type": source.source_type,
                    "candidates": len(candidates),
                    "manual_review_candidates": source_manual_review_candidates,
                    "source_run_id": run.id if run else None,
                    "status": "completed",
                }
            )

            for item in candidates:
                try:
                    if _is_duplicate(db, item):
                        skipped += 1
                        source_skipped += 1
                        _record_source_run_item(db, run, item, "duplicate")
                        continue

                    row = _create_opportunity(db, source, item)
                    created += 1
                    source_created += 1
                    action = "created"
                    if item.get("manual_review_needed", False):
                        source_manual_review_created += 1
                    if options.auto_score:
                        score_and_store_opportunity(db, row, profile)
                        scored += 1
                        source_scored += 1
                        action = "scored"
                    _record_source_run_item(db, run, item, action, opportunity_id=row.id)
                except Exception as exc:
                    _record_source_run_item(db, run, item, "failed", error_message=_safe_error_message(exc))

            _apply_run_counts(
                run,
                candidates_found=len(candidates),
                created=source_created,
                duplicates_skipped=source_skipped,
                scored=source_scored,
                manual_review_candidates=source_manual_review_candidates,
                manual_review_created=source_manual_review_created,
            )
            _finish_source_run(db, run, "completed")
        except Exception as exc:
            error_message = _safe_error_message(exc)
            diagnostics.append(
                {
                    "source": source.name,
                    "source_type": source.source_type,
                    "candidates": len(candidates),
                    "manual_review_candidates": source_manual_review_candidates,
                    "source_run_id": run.id if run else None,
                    "status": "failed",
                    "error_message": error_message,
                }
            )
            _finish_source_run(db, run, "failed", error_message)

    if created == 0 and sources and options.allow_mock_fallback:
        fallback_source = sources[0]
        fallback_run = source_runs[0][1] if source_runs else None
        mock_fallback_used = True
        fallback_created = 0
        fallback_skipped = 0
        fallback_scored = 0
        fallback_manual_review_created = 0
        fallback_candidates = mock_candidates(fallback_source.name, fallback_source.url)
        for item in fallback_candidates:
            if _is_duplicate(db, item):
                skipped += 1
                fallback_skipped += 1
                _record_source_run_item(db, fallback_run, item, "duplicate")
                continue
            row = _create_opportunity(db, fallback_source, item)
            created += 1
            fallback_created += 1
            if item.get("manual_review_needed", False):
                fallback_manual_review_created += 1
            if options.auto_score:
                score_and_store_opportunity(db, row, profile)
                scored += 1
                fallback_scored += 1
                _record_source_run_item(db, fallback_run, item, "scored", opportunity_id=row.id)
            else:
                _record_source_run_item(db, fallback_run, item, "created", opportunity_id=row.id)
        if fallback_run:
            fallback_run.mock_fallback_used = True
            _apply_run_counts(
                fallback_run,
                candidates_found=len(fallback_candidates),
                created=fallback_created,
                duplicates_skipped=fallback_skipped,
                scored=fallback_scored,
                manual_review_candidates=sum(
                    1 for item in fallback_candidates if item.get("manual_review_needed", False)
                ),
                manual_review_created=fallback_manual_review_created,
            )
            db.commit()

    source_run_ids = [run.id for _, run in source_runs if run]
    result = {
        "ok": True,
        "created": created,
        "duplicates_skipped": skipped,
        "sources": len(sources),
        "profile_name": profile.get("name", "Unknown"),
        "scored": scored,
        "mock_fallback_used": mock_fallback_used,
        "diagnostics": diagnostics,
    }
    if source_run_ids:
        result["source_run_id"] = source_run_ids[0]
    return result
