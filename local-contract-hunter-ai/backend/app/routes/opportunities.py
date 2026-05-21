from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.opportunity import OpportunityRead, OpportunityStatusUpdate
from app.schemas.proposal_checklist import ProposalChecklistRead
from app.services.proposal_checklist_service import build_proposal_checklist


router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityRead])
def list_opportunities(db: Session = Depends(get_db)):
    opportunities = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.score))
        .order_by(Opportunity.created_at.desc())
        .all()
    )
    for opp in opportunities:
        if opp.score and isinstance(opp.score.next_steps, str):
            try:
                opp.score.next_steps = json.loads(opp.score.next_steps)
            except Exception:
                opp.score.next_steps = []
    return opportunities


@router.get("/{opportunity_id}/checklist", response_model=ProposalChecklistRead)
def get_opportunity_checklist(opportunity_id: int, db: Session = Depends(get_db)):
    opp = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.score))
        .filter(Opportunity.id == opportunity_id)
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return build_proposal_checklist(opp)


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    opp = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.score))
        .filter(Opportunity.id == opportunity_id)
        .first()
    )
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.score and isinstance(opp.score.next_steps, str):
        try:
            opp.score.next_steps = json.loads(opp.score.next_steps)
        except Exception:
            opp.score.next_steps = []
    return opp


@router.patch("/{opportunity_id}/status", response_model=OpportunityRead)
def update_opportunity_status(
    opportunity_id: int,
    payload: OpportunityStatusUpdate,
    db: Session = Depends(get_db),
):
    allowed = {"Saved", "Skipped", "Pursue", "Watch"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of {sorted(allowed)}")

    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.status = payload.status
    db.commit()
    db.refresh(opp)
    return opp
