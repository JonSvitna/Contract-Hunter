from __future__ import annotations

from pydantic import BaseModel, Field


class SchedulerConfig(BaseModel):
    enabled: bool = False
    frequency_minutes: int = Field(default=1440, ge=15, le=10080)
    max_runs_per_day: int = Field(default=2, ge=1, le=48)
    jitter_seconds: int = Field(default=30, ge=0, le=300)
    last_run_at: str | None = None
    last_run_day: str | None = None
    runs_today: int = Field(default=0, ge=0, le=1000)
    last_result: str | None = None
    notes: str | None = None


class SchedulerUpdate(BaseModel):
    enabled: bool | None = None
    frequency_minutes: int | None = Field(default=None, ge=15, le=10080)
    max_runs_per_day: int | None = Field(default=None, ge=1, le=48)
    jitter_seconds: int | None = Field(default=None, ge=0, le=300)
    runs_today: int | None = Field(default=None, ge=0, le=1000)
    last_run_at: str | None = None
    last_run_day: str | None = None
    last_result: str | None = None
    notes: str | None = None


class SchedulerStatus(BaseModel):
    enabled: bool
    frequency_minutes: int
    max_runs_per_day: int
    jitter_seconds: int
    runs_today: int
    last_run_at: str | None = None
    last_run_day: str | None = None
    last_result: str | None = None
    next_run_at: str | None = None
    can_run_now: bool
    reason: str
