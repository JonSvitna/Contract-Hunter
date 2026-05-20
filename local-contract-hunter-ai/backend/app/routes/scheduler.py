from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.schemas.scheduler import SchedulerConfig, SchedulerStatus, SchedulerUpdate
from app.services.source_service import load_scheduler_config, save_scheduler_config


router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("", response_model=SchedulerConfig)
def get_scheduler_config():
    payload = load_scheduler_config()
    return SchedulerConfig(**payload)


@router.patch("", response_model=SchedulerConfig)
def update_scheduler_config(update: SchedulerUpdate):
    current = SchedulerConfig(**load_scheduler_config()).model_dump()
    for key, value in update.model_dump(exclude_unset=True).items():
        current[key] = value
    validated = SchedulerConfig(**current)
    save_scheduler_config(validated.model_dump())
    return validated


@router.post("/toggle", response_model=SchedulerConfig)
def toggle_scheduler():
    current = SchedulerConfig(**load_scheduler_config())
    updated = current.model_copy(update={"enabled": not current.enabled})
    save_scheduler_config(updated.model_dump())
    return updated


@router.get("/status", response_model=SchedulerStatus)
def get_scheduler_status():
    config = SchedulerConfig(**load_scheduler_config())
    now = datetime.now(timezone.utc)

    next_run_at = None
    next_run_dt = None
    if config.last_run_at:
        try:
            parsed = datetime.fromisoformat(config.last_run_at)
            next_run_dt = parsed + timedelta(minutes=config.frequency_minutes)
            next_run_at = next_run_dt.isoformat()
        except ValueError:
            next_run_at = None

    can_run = True
    reason = "ready"
    if not config.enabled:
        can_run = False
        reason = "scheduler_disabled"
    elif config.last_run_day == now.date().isoformat() and config.runs_today >= config.max_runs_per_day:
        can_run = False
        reason = "max_runs_reached_today"
    elif next_run_dt and now < next_run_dt:
        can_run = False
        reason = "too_soon_for_frequency"

    return SchedulerStatus(
        enabled=config.enabled,
        frequency_minutes=config.frequency_minutes,
        max_runs_per_day=config.max_runs_per_day,
        jitter_seconds=config.jitter_seconds,
        runs_today=config.runs_today,
        last_run_at=config.last_run_at,
        last_run_day=config.last_run_day,
        last_result=config.last_result,
        next_run_at=next_run_at,
        can_run_now=can_run,
        reason=reason,
    )
