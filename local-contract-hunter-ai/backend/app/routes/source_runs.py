from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.source_run import SourceRun
from app.routes.sources import source_run_summary
from app.schemas.source_run import SourceRunDetailRead


router = APIRouter(prefix="/source-runs", tags=["source-runs"])


@router.get("/{run_id}", response_model=SourceRunDetailRead)
def get_source_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(SourceRun)
        .options(joinedload(SourceRun.items))
        .filter(SourceRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Source run not found")
    return {
        **source_run_summary(run),
        "source_id": run.source_id,
        "source_name": run.source_name,
        "source_type": run.source_type,
        "source_url": run.source_url,
        "auto_score": run.auto_score,
        "mock_fallback_allowed": run.mock_fallback_allowed,
        "mock_fallback_used": run.mock_fallback_used,
        "items": run.items,
    }
