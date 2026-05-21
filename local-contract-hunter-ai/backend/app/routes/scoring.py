from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.opportunity import Opportunity
from app.services.score_persistence import score_and_store_opportunity
from app.services.source_service import load_business_profile


router = APIRouter(prefix="/opportunities", tags=["scoring"])


@router.post("/{opportunity_id}/score")
def score_single_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    profile = load_business_profile()
    payload = score_and_store_opportunity(db, opportunity, profile)
    return {"ok": True, "score": payload}
