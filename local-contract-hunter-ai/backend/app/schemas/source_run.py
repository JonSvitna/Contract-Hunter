from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceRunSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    candidates_found: int
    created: int
    duplicates_skipped: int
    scored: int
    manual_review_candidates: int
    manual_review_created: int
    manual_review_fallback_rate: float
    error_message: str | None


class SourceRunItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int | None
    action: str
    title: str | None
    agency: str | None
    opportunity_url: str | None
    due_date: date | None
    extraction_confidence: float | None
    manual_review_needed: bool
    error_message: str | None


class SourceRunDetailRead(SourceRunSummaryRead):
    source_id: int | None
    source_name: str
    source_type: str
    source_url: str
    auto_score: bool
    mock_fallback_allowed: bool
    mock_fallback_used: bool
    items: list[SourceRunItemRead] = Field(default_factory=list)


class SourceDashboardItem(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    active: bool
    search_delay_seconds: float
    notes: str | None
    last_run: SourceRunSummaryRead | None


class SourceDashboardRead(BaseModel):
    items: list[SourceDashboardItem]
