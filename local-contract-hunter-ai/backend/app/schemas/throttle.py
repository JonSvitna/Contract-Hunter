from __future__ import annotations

from pydantic import BaseModel, Field


class ThrottleControl(BaseModel):
    max_candidate_links: int = Field(default=120, ge=20, le=500)
    page_timeout_ms: int = Field(default=20000, ge=5000, le=120000)
    body_timeout_ms: int = Field(default=5000, ge=2000, le=60000)


class ThrottleConfig(BaseModel):
    defaults: ThrottleControl
    by_source: dict[str, ThrottleControl] = Field(default_factory=dict)


class ThrottleControlUpdate(BaseModel):
    max_candidate_links: int | None = Field(default=None, ge=20, le=500)
    page_timeout_ms: int | None = Field(default=None, ge=5000, le=120000)
    body_timeout_ms: int | None = Field(default=None, ge=2000, le=60000)
