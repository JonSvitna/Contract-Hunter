from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.opportunity import Opportunity
from app.schemas.digest import DigestPreviewRead
from app.services.digest_service import select_digest_candidates


router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/preview", response_model=DigestPreviewRead)
def get_digest_preview(db: Session = Depends(get_db)):
    opportunities = (
        db.query(Opportunity)
        .options(joinedload(Opportunity.score))
        .order_by(Opportunity.created_at.desc(), Opportunity.id.asc())
        .all()
    )
    return DigestPreviewRead(
        generated_at=datetime.now(timezone.utc),
        candidates=select_digest_candidates(opportunities),
    )
