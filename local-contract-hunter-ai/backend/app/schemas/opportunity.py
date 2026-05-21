from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.score import OpportunityScoreRead


class OpportunityRead(BaseModel):
    id: int
    title: str
    agency: str
    source_name: str
    source_url: str
    opportunity_url: str | None
    external_id: str | None = None
    source_status: str | None = None
    last_seen_at: datetime | None = None
    updated_at: datetime | None = None
    due_date: date | None
    description_snippet: str | None
    status: str
    extraction_confidence: float
    manual_review_needed: bool
    score: OpportunityScoreRead | None = None

    class Config:
        from_attributes = True


class OpportunityStatusUpdate(BaseModel):
    status: str
