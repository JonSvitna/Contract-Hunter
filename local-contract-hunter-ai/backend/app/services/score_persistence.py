from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.services.scoring_service import score_opportunity


def score_and_store_opportunity(
    db: Session,
    opportunity: Opportunity,
    profile: dict,
) -> dict:
    payload = score_opportunity(opportunity, profile)
    existing = (
        db.query(OpportunityScore)
        .filter(OpportunityScore.opportunity_id == opportunity.id)
        .first()
    )
    serialized_payload = {
        key: json.dumps(value) if key == "next_steps" else value
        for key, value in payload.items()
    }

    if existing:
        for key, value in serialized_payload.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = OpportunityScore(
            opportunity_id=opportunity.id,
            **serialized_payload,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return payload
