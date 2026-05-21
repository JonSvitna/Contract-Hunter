from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.opportunity import (
    OpportunityRead,
    OpportunitySearchResult,
    OpportunityStatusUpdate,
    OpportunitySummary,
)
from app.schemas.proposal_checklist import ProposalChecklistRead
from app.services.opportunity_query_service import (
    OpportunitySearchParams,
    normalize_score_next_steps,
    normalize_score_next_steps_for_many,
    opportunity_summary,
    search_opportunities,
    split_multi,
)
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
    return normalize_score_next_steps_for_many(opportunities)


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


@router.get("/search", response_model=OpportunitySearchResult)
def search_opportunities_route(
    page: int = Query(default=1),
    page_size: int = Query(default=25),
    q: str | None = None,
    bpm_id: str | None = None,
    agency: str | None = None,
    source: str | None = None,
    status: Annotated[list[str] | None, Query()] = None,
    recommendation: Annotated[list[str] | None, Query()] = None,
    source_status: Annotated[list[str] | None, Query()] = None,
    manual_review: bool | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    min_fit_score: int | None = None,
    max_fit_score: int | None = None,
    min_skill_match: int | None = None,
    min_solo_fit: int | None = None,
    min_revenue_fit: int | None = None,
    min_local_fit: int | None = None,
    max_deadline_risk: int | None = None,
    max_complexity_risk: int | None = None,
    sort: str = "created_at",
    direction: str = "desc",
    db: Session = Depends(get_db),
):
    params = OpportunitySearchParams(
        page=page,
        page_size=page_size,
        q=q.strip() if q else None,
        bpm_id=bpm_id.strip() if bpm_id else None,
        agency=agency.strip() if agency else None,
        source=source.strip() if source else None,
        status=split_multi(status),
        recommendation=split_multi(recommendation),
        source_status=split_multi(source_status),
        manual_review=manual_review,
        due_from=due_from,
        due_to=due_to,
        created_from=created_from,
        created_to=created_to,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_fit_score=min_fit_score,
        max_fit_score=max_fit_score,
        min_skill_match=min_skill_match,
        min_solo_fit=min_solo_fit,
        min_revenue_fit=min_revenue_fit,
        min_local_fit=min_local_fit,
        max_deadline_risk=max_deadline_risk,
        max_complexity_risk=max_complexity_risk,
        sort=sort,
        direction=direction,
    )
    return search_opportunities(db, params)


@router.get("/summary", response_model=OpportunitySummary)
def get_opportunity_summary(db: Session = Depends(get_db)):
    return opportunity_summary(db)


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
    normalize_score_next_steps(opp)
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
