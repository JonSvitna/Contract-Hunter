from __future__ import annotations

from pydantic import BaseModel


class OpportunityScoreRead(BaseModel):
    fit_score: int
    skill_match: int
    solo_fit: int
    revenue_fit: int
    local_fit: int
    deadline_risk: int
    complexity_risk: int
    past_performance_risk: str
    recommendation: str
    reasoning: str
    next_steps: list[str]

    class Config:
        from_attributes = True
