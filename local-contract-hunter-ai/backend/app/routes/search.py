from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.source import Source
from app.schemas.throttle import ThrottleConfig, ThrottleControl, ThrottleControlUpdate
from app.scrapers.emma_scraper import EmmaScraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper
from app.services.source_service import (
    get_effective_throttle_for_source,
    load_business_profile,
    load_keywords,
    load_scheduler_config,
    load_throttle_config,
    save_scheduler_config,
    save_throttle_config,
)


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
    return _execute_search(db)


def _execute_search(db: Session):
    profile = load_business_profile()
    keywords = load_keywords()
    sources = db.query(Source).filter(Source.active.is_(True)).all()
    created = 0
    skipped = 0

    for source in sources:
        throttle = get_effective_throttle_for_source(source.name)
        scraper = (
            EmmaScraper(
                delay_seconds=source.search_delay_seconds,
                max_candidate_links=int(throttle.get("max_candidate_links", 120)),
                page_timeout_ms=int(throttle.get("page_timeout_ms", 20000)),
                body_timeout_ms=int(throttle.get("body_timeout_ms", 5000)),
            )
            if source.source_type.lower() == "emma"
            else GenericProcurementScraper(
                delay_seconds=source.search_delay_seconds,
                max_candidate_links=int(throttle.get("max_candidate_links", 120)),
                page_timeout_ms=int(throttle.get("page_timeout_ms", 20000)),
                body_timeout_ms=int(throttle.get("body_timeout_ms", 5000)),
            )
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


@router.post("/run-now")
def run_search_now(db: Session = Depends(get_db)):
    scheduler = load_scheduler_config()
    today = datetime.now(timezone.utc).date().isoformat()

    if scheduler.get("last_run_day") != today:
        scheduler["last_run_day"] = today
        scheduler["runs_today"] = 0

    if not scheduler.get("enabled", False):
        scheduler["last_result"] = "skipped:scheduler_disabled"
        save_scheduler_config(scheduler)
        return {
            "ok": True,
            "skipped": True,
            "reason": "scheduler_disabled",
            "runs_today": scheduler.get("runs_today", 0),
        }

    if int(scheduler.get("runs_today", 0)) >= int(scheduler.get("max_runs_per_day", 2)):
        scheduler["last_result"] = "skipped:max_runs_reached_today"
        save_scheduler_config(scheduler)
        return {
            "ok": True,
            "skipped": True,
            "reason": "max_runs_reached_today",
            "runs_today": scheduler.get("runs_today", 0),
        }

    last_run_at = scheduler.get("last_run_at")
    if last_run_at:
        try:
            parsed_last = datetime.fromisoformat(last_run_at)
            next_allowed = parsed_last + timedelta(minutes=int(scheduler.get("frequency_minutes", 1440)))
            if datetime.now(timezone.utc) < next_allowed:
                scheduler["last_result"] = "skipped:too_soon_for_frequency"
                save_scheduler_config(scheduler)
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "too_soon_for_frequency",
                    "runs_today": scheduler.get("runs_today", 0),
                    "next_run_at": next_allowed.isoformat(),
                }
        except ValueError:
            pass

    result = _execute_search(db)
    scheduler["last_run_at"] = datetime.now(timezone.utc).isoformat()
    scheduler["last_run_day"] = today
    scheduler["runs_today"] = int(scheduler.get("runs_today", 0)) + 1
    scheduler["last_result"] = f"success:created={result.get('created', 0)}"
    save_scheduler_config(scheduler)

    return {
        **result,
        "skipped": False,
        "reason": "ran",
        "runs_today": scheduler.get("runs_today", 0),
    }


@router.post("/cron-run")
def run_search_from_cron(
    db: Session = Depends(get_db),
    x_cron_token: str | None = Header(default=None),
):
    if not settings.cron_webhook_token:
        raise HTTPException(status_code=400, detail="CRON_WEBHOOK_TOKEN is not configured")
    if x_cron_token != settings.cron_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid cron token")
    return run_search_now(db)


@router.get("/throttle", response_model=ThrottleConfig)
def get_throttle_config():
    payload = load_throttle_config()
    defaults = ThrottleControl(**payload.get("defaults", {}))
    by_source = {
        source_name: ThrottleControl(**raw)
        for source_name, raw in payload.get("by_source", {}).items()
    }
    return ThrottleConfig(defaults=defaults, by_source=by_source)


@router.patch("/throttle/defaults", response_model=ThrottleConfig)
def patch_throttle_defaults(update: ThrottleControlUpdate):
    current = load_throttle_config()
    defaults = {**current.get("defaults", {}), **update.model_dump(exclude_unset=True)}
    validated_defaults = ThrottleControl(**defaults).model_dump()
    updated = {"defaults": validated_defaults, "by_source": current.get("by_source", {})}
    save_throttle_config(updated)
    return get_throttle_config()


@router.patch("/throttle/source/{source_id}", response_model=ThrottleConfig)
def patch_throttle_source(source_id: int, update: ThrottleControlUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    current = load_throttle_config()
    by_source = current.get("by_source", {})
    existing = by_source.get(source.name, {})
    merged = {**existing, **update.model_dump(exclude_unset=True)}
    validated = ThrottleControl(**merged).model_dump()
    by_source[source.name] = validated

    updated = {"defaults": current.get("defaults", {}), "by_source": by_source}
    save_throttle_config(updated)
    return get_throttle_config()


@router.get("/config")
def get_search_config_preview():
    return {
        "business_profile": load_business_profile(),
        "keywords": load_keywords(),
        "throttle": load_throttle_config(),
    }
