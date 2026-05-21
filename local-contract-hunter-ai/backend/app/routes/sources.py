from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.source import Source
from app.models.source_run import SourceRun
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.schemas.source_run import SourceDashboardRead, SourceRunSummaryRead
from app.services.source_service import sync_missing_seed_sources


router = APIRouter(prefix="/sources", tags=["sources"])


def source_run_summary(run: SourceRun) -> dict:
    fallback_rate = 0.0
    if run.candidates_found:
        fallback_rate = run.manual_review_candidates / run.candidates_found
    return {
        "id": run.id,
        "run_kind": run.run_kind,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "candidates_found": run.candidates_found,
        "created": run.created,
        "duplicates_skipped": run.duplicates_skipped,
        "scored": run.scored,
        "manual_review_candidates": run.manual_review_candidates,
        "manual_review_created": run.manual_review_created,
        "manual_review_fallback_rate": fallback_rate,
        "error_message": run.error_message,
    }


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).order_by(Source.name.asc()).all()


@router.post("", response_model=SourceRead)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    exists = db.query(Source).filter(Source.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Source already exists")
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/sync-defaults")
def sync_default_sources(db: Session = Depends(get_db)):
    return {"created": sync_missing_seed_sources(db)}


@router.get("/dashboard", response_model=SourceDashboardRead)
def source_dashboard(db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.name.asc()).all()
    items = []
    for source in sources:
        latest_run = (
            db.query(SourceRun)
            .filter(SourceRun.source_id == source.id)
            .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
            .first()
        )
        items.append(
            {
                "id": source.id,
                "name": source.name,
                "url": source.url,
                "source_type": source.source_type,
                "active": source.active,
                "search_delay_seconds": source.search_delay_seconds,
                "notes": source.notes,
                "last_run": source_run_summary(latest_run) if latest_run else None,
            }
        )
    return {"items": items}


@router.get("/{source_id}/runs", response_model=list[SourceRunSummaryRead])
def list_source_runs(
    source_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    runs = (
        db.query(SourceRun)
        .filter(SourceRun.source_id == source_id)
        .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
        .limit(limit)
        .all()
    )
    return [source_run_summary(run) for run in runs]


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source
