from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.services.scoring_service import score_opportunity
from app.services.source_service import load_business_profile


router = APIRouter(prefix="/opportunities", tags=["scoring"])


@router.post("/{opportunity_id}/score")
def score_single_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    profile = load_business_profile()
    payload = score_opportunity(opportunity, profile)

    existing = (
        db.query(OpportunityScore)
        .filter(OpportunityScore.opportunity_id == opportunity_id)
        .first()
    )
    if existing:
        for key, value in payload.items():
            setattr(existing, key, json.dumps(value) if key == "next_steps" else value)
        row = existing
    else:
        row = OpportunityScore(
            opportunity_id=opportunity_id,
            **{k: json.dumps(v) if k == "next_steps" else v for k, v in payload.items()},
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return {"ok": True, "score": payload}
