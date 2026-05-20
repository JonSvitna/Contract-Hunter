from __future__ import annotations

from fastapi import APIRouter

from app.schemas.scheduler import SchedulerConfig, SchedulerUpdate
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
