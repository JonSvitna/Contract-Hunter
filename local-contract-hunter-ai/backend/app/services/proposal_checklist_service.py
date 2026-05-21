from __future__ import annotations

import json

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.schemas.proposal_checklist import ProposalChecklistRead


BASE_CHECKLIST_ITEMS = [
    "Confirm scope, deliverables, and eligibility on the original posting.",
    "Verify due date, submission portal, addenda, and question deadline.",
    "Identify required attachments: pricing, references, certifications, and forms.",
    "Check past performance and staffing requirements against solo-consultant capacity.",
]

DEFAULT_NEXT_ACTIONS = [
    "Open the original posting and verify details before changing status.",
    "Confirm submission steps and required attachments.",
    "Draft a short go/no-go note from the verified requirements.",
]


def _score_next_steps(score: OpportunityScore) -> list[str]:
    if isinstance(score.next_steps, list):
        return [str(step) for step in score.next_steps if str(step).strip()][:3]
    if isinstance(score.next_steps, str):
        try:
            parsed = json.loads(score.next_steps)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(step) for step in parsed if str(step).strip()][:3]
    return []


def _bid_recommendation(opportunity: Opportunity) -> str:
    score = opportunity.score
    if not score:
        return "Manual Review"
    if opportunity.due_date is None:
        return "Manual Review"
    if score.deadline_risk >= 85 or score.complexity_risk >= 80:
        return "No Bid"
    if score.recommendation == "Pursue":
        return "Bid"
    if score.recommendation == "Watch":
        return "Watch"
    if score.recommendation == "Skip":
        return "No Bid"
    return "Manual Review"


def _risk_flags(opportunity: Opportunity) -> list[str]:
    flags: list[str] = []
    score = opportunity.score
    if not score:
        flags.append("Score missing; run scoring before deciding.")
    if opportunity.manual_review_needed:
        flags.append("Source extraction requires manual review.")
    if opportunity.due_date is None:
        flags.append("Due date is missing; verify closing date before bidding.")
    if score:
        if score.deadline_risk >= 85:
            flags.append("Tight deadline risk.")
        if score.complexity_risk >= 80:
            flags.append("High complexity risk for a solo consultancy.")
        if score.past_performance_risk == "High":
            flags.append("High past-performance requirement risk.")
    return flags


def _rationale(opportunity: Opportunity, bid_recommendation: str, risk_flags: list[str]) -> str:
    score = opportunity.score
    if not score:
        return "Manual review required because no score exists yet."
    if risk_flags and bid_recommendation == "No Bid":
        return f"{score.recommendation} candidate blocked by proposal risk: {risk_flags[0]}"
    if risk_flags and bid_recommendation == "Manual Review":
        return f"{score.recommendation} candidate needs validation before bid/no-bid: {risk_flags[0]}"
    return f"{score.recommendation} candidate with fit score {score.fit_score}."


def build_proposal_checklist(opportunity: Opportunity) -> ProposalChecklistRead:
    risk_flags = _risk_flags(opportunity)
    bid_recommendation = _bid_recommendation(opportunity)
    next_actions = _score_next_steps(opportunity.score) if opportunity.score else []

    return ProposalChecklistRead(
        opportunity_id=opportunity.id,
        bid_recommendation=bid_recommendation,
        checklist_items=BASE_CHECKLIST_ITEMS,
        risk_flags=risk_flags,
        next_actions=next_actions or DEFAULT_NEXT_ACTIONS,
        rationale=_rationale(opportunity, bid_recommendation, risk_flags),
    )
