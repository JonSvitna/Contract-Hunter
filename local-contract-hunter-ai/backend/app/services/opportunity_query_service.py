from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore

VALID_SORTS = {
    "created_at",
    "updated_at",
    "due_date",
    "fit_score",
    "agency",
    "confidence",
    "source_status",
}
VALID_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True)
class OpportunitySearchParams:
    page: int = 1
    page_size: int = 25
    q: str | None = None
    bpm_id: str | None = None
    agency: str | None = None
    source: str | None = None
    status: tuple[str, ...] = ()
    recommendation: tuple[str, ...] = ()
    source_status: tuple[str, ...] = ()
    manual_review: bool | None = None
    due_from: date | None = None
    due_to: date | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    min_fit_score: int | None = None
    max_fit_score: int | None = None
    min_skill_match: int | None = None
    min_solo_fit: int | None = None
    min_revenue_fit: int | None = None
    min_local_fit: int | None = None
    max_deadline_risk: int | None = None
    max_complexity_risk: int | None = None
    sort: str = "created_at"
    direction: str = "desc"


def split_multi(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    result: list[str] = []
    for value in values:
        for part in value.split(","):
            stripped = part.strip()
            if stripped:
                result.append(stripped)
    return tuple(result)


def normalize_score_next_steps(opportunity: Opportunity) -> None:
    if opportunity.score and isinstance(opportunity.score.next_steps, str):
        try:
            opportunity.score.next_steps = json.loads(opportunity.score.next_steps)
        except Exception:
            opportunity.score.next_steps = []


def normalize_score_next_steps_for_many(opportunities: list[Opportunity]) -> list[Opportunity]:
    for opportunity in opportunities:
        normalize_score_next_steps(opportunity)
    return opportunities


def _validate_params(params: OpportunitySearchParams) -> None:
    if params.page_size < 5 or params.page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 5 and 100")
    if params.sort not in VALID_SORTS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {sorted(VALID_SORTS)}")
    if params.direction not in VALID_DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction must be asc or desc")


def _score_filters_present(params: OpportunitySearchParams) -> bool:
    return any(
        value is not None
        for value in (
            params.min_fit_score,
            params.max_fit_score,
            params.min_skill_match,
            params.min_solo_fit,
            params.min_revenue_fit,
            params.min_local_fit,
            params.max_deadline_risk,
            params.max_complexity_risk,
        )
    ) or bool(params.recommendation)


def _base_query(db: Session, params: OpportunitySearchParams):
    query = db.query(Opportunity).options(joinedload(Opportunity.score))
    if _score_filters_present(params) or params.sort == "fit_score":
        query = query.outerjoin(OpportunityScore)

    if params.q:
        pattern = f"%{params.q}%"
        query = query.filter(
            or_(
                Opportunity.title.ilike(pattern),
                Opportunity.agency.ilike(pattern),
                Opportunity.description_snippet.ilike(pattern),
                Opportunity.source_name.ilike(pattern),
                Opportunity.external_id.ilike(pattern),
            )
        )
    if params.bpm_id:
        query = query.filter(Opportunity.external_id.ilike(f"%{params.bpm_id}%"))
    if params.agency:
        query = query.filter(Opportunity.agency.ilike(f"%{params.agency}%"))
    if params.source:
        query = query.filter(Opportunity.source_name == params.source)
    if params.status:
        query = query.filter(Opportunity.status.in_(params.status))
    if params.source_status:
        query = query.filter(Opportunity.source_status.in_(params.source_status))
    if params.manual_review is not None:
        query = query.filter(Opportunity.manual_review_needed.is_(params.manual_review))
    if params.due_from:
        query = query.filter(Opportunity.due_date >= params.due_from)
    if params.due_to:
        query = query.filter(Opportunity.due_date <= params.due_to)
    if params.created_from:
        query = query.filter(Opportunity.created_at >= params.created_from)
    if params.created_to:
        query = query.filter(Opportunity.created_at <= params.created_to)
    if params.min_confidence is not None:
        query = query.filter(Opportunity.extraction_confidence >= params.min_confidence)
    if params.max_confidence is not None:
        query = query.filter(Opportunity.extraction_confidence <= params.max_confidence)
    if params.recommendation:
        if "Manual Review" in params.recommendation:
            query = query.filter(
                or_(
                    OpportunityScore.recommendation.in_(params.recommendation),
                    OpportunityScore.id.is_(None),
                )
            )
        else:
            query = query.filter(OpportunityScore.recommendation.in_(params.recommendation))
    if params.min_fit_score is not None:
        query = query.filter(OpportunityScore.fit_score >= params.min_fit_score)
    if params.max_fit_score is not None:
        query = query.filter(OpportunityScore.fit_score <= params.max_fit_score)
    if params.min_skill_match is not None:
        query = query.filter(OpportunityScore.skill_match >= params.min_skill_match)
    if params.min_solo_fit is not None:
        query = query.filter(OpportunityScore.solo_fit >= params.min_solo_fit)
    if params.min_revenue_fit is not None:
        query = query.filter(OpportunityScore.revenue_fit >= params.min_revenue_fit)
    if params.min_local_fit is not None:
        query = query.filter(OpportunityScore.local_fit >= params.min_local_fit)
    if params.max_deadline_risk is not None:
        query = query.filter(OpportunityScore.deadline_risk <= params.max_deadline_risk)
    if params.max_complexity_risk is not None:
        query = query.filter(OpportunityScore.complexity_risk <= params.max_complexity_risk)
    return query


def _sort_expression(sort: str):
    if sort == "fit_score":
        return OpportunityScore.fit_score
    if sort == "agency":
        return Opportunity.agency
    if sort == "confidence":
        return Opportunity.extraction_confidence
    if sort == "source_status":
        return Opportunity.source_status
    if sort == "due_date":
        return Opportunity.due_date
    if sort == "updated_at":
        return Opportunity.updated_at
    return Opportunity.created_at


def search_opportunities(db: Session, params: OpportunitySearchParams) -> dict:
    _validate_params(params)
    page = max(1, params.page)
    query = _base_query(db, params)
    total = query.count()
    sort_expression = _sort_expression(params.sort)
    ordered = desc(sort_expression) if params.direction == "desc" else asc(sort_expression)
    items = (
        query.order_by(ordered, Opportunity.id.desc())
        .offset((page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return {
        "items": normalize_score_next_steps_for_many(items),
        "total": total,
        "page": page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if total else 0,
    }


def opportunity_summary(db: Session) -> dict:
    today = date.today()
    total = db.query(func.count(Opportunity.id)).scalar() or 0
    pursue = (
        db.query(func.count(Opportunity.id))
        .join(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(OpportunityScore.recommendation == "Pursue")
        .scalar()
        or 0
    )
    watch = (
        db.query(func.count(Opportunity.id))
        .join(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(OpportunityScore.recommendation == "Watch")
        .scalar()
        or 0
    )
    skipped = db.query(func.count(Opportunity.id)).filter(Opportunity.status == "Skipped").scalar() or 0
    manual_review = (
        db.query(func.count(Opportunity.id))
        .outerjoin(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(
            or_(
                OpportunityScore.recommendation == "Manual Review",
                OpportunityScore.id.is_(None),
                Opportunity.manual_review_needed.is_(True),
            )
        )
        .scalar()
        or 0
    )
    upcoming_deadlines = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.due_date.isnot(None), Opportunity.due_date >= today)
        .scalar()
        or 0
    )
    return {
        "total": total,
        "pursue": pursue,
        "watch": watch,
        "skipped": skipped,
        "manual_review": manual_review,
        "upcoming_deadlines": upcoming_deadlines,
    }
