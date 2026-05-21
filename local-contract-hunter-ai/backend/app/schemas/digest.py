from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DigestCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    agency: str
    source_name: str
    opportunity_url: str | None
    due_date: date | None
    status: str
    fit_score: int
    recommendation: str
    reasoning: str


class DigestPreviewRead(BaseModel):
    generated_at: datetime
    candidates: list[DigestCandidateRead]
