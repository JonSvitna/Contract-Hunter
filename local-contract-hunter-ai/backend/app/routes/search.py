from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.source import Source
from app.schemas.throttle import ThrottleConfig, ThrottleControl, ThrottleControlUpdate
from app.services.search_service import SearchRunOptions, execute_search
from app.services.source_service import (
    load_business_profile,
    load_keywords,
    load_scheduler_config,
    load_throttle_config,
    save_scheduler_config,
    save_throttle_config,
)


router = APIRouter(prefix="/search", tags=["search"])


class SourceValidationRequest(BaseModel):
    source_name: str = Field(..., min_length=1)
    auto_score: bool = True


@router.post("/run")
def run_search(db: Session = Depends(get_db)):
    return execute_search(db, SearchRunOptions())


@router.post("/validate/emma")
def validate_emma_search(db: Session = Depends(get_db)):
    return execute_search(
        db,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )


@router.post("/validate/source")
def validate_source_search(payload: SourceValidationRequest, db: Session = Depends(get_db)):
    source_name = payload.source_name.strip()
    source = db.query(Source).filter(Source.name == source_name, Source.active.is_(True)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Active source not found")
    if source.source_type.lower() != "generic":
        raise HTTPException(status_code=400, detail="Source must be a configured generic local source")

    return execute_search(
        db,
        SearchRunOptions(
            source_type="generic",
            source_name=source.name,
            allow_mock_fallback=False,
            auto_score=payload.auto_score,
        ),
    )


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

    result = execute_search(db, SearchRunOptions())
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
