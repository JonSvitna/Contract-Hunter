from __future__ import annotations

from pydantic import BaseModel


class ProposalChecklistRead(BaseModel):
    opportunity_id: int
    bid_recommendation: str
    checklist_items: list[str]
    risk_flags: list[str]
    next_actions: list[str]
    rationale: str
