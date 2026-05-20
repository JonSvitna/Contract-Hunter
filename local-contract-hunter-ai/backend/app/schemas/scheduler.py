from __future__ import annotations

from pydantic import BaseModel, Field


class SchedulerConfig(BaseModel):
    enabled: bool = False
    frequency_minutes: int = Field(default=1440, ge=15, le=10080)
    max_runs_per_day: int = Field(default=2, ge=1, le=48)
    jitter_seconds: int = Field(default=30, ge=0, le=300)
    notes: str | None = None


class SchedulerUpdate(BaseModel):
    enabled: bool | None = None
    frequency_minutes: int | None = Field(default=None, ge=15, le=10080)
    max_runs_per_day: int | None = Field(default=None, ge=1, le=48)
    jitter_seconds: int | None = Field(default=None, ge=0, le=300)
    notes: str | None = None
