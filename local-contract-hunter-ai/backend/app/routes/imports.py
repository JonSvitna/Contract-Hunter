from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.import_run import ImportRun
from app.schemas.imports import (
    EmmaExcelImportRequest,
    EmmaExcelImportResult,
    ImportRunDetailRead,
    ImportRunRead,
)
from app.services.emma_excel_import_service import import_emma_excel, import_emma_excel_upload
from app.services.source_service import load_business_profile

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/emma-excel/upload", response_model=EmmaExcelImportResult)
async def upload_emma_excel_file(
    file: UploadFile = File(...),
    auto_score: bool = Form(True),
    db: Session = Depends(get_db),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="eMMA import requires a .xlsx file")

    contents = await file.read()
    try:
        return import_emma_excel_upload(
            db,
            contents,
            filename=filename,
            content_type=file.content_type,
            profile=load_business_profile(),
            auto_score=auto_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/emma-excel")
def import_emma_excel_file(payload: EmmaExcelImportRequest, db: Session = Depends(get_db)):
    try:
        return import_emma_excel(
            db,
            payload.path,
            profile=load_business_profile(),
            auto_score=payload.auto_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=list[ImportRunRead])
def list_import_runs(db: Session = Depends(get_db)):
    return (
        db.query(ImportRun)
        .order_by(ImportRun.uploaded_at.desc(), ImportRun.id.desc())
        .limit(10)
        .all()
    )


@router.get("/runs/{run_id}", response_model=ImportRunDetailRead)
def get_import_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(ImportRun)
        .options(joinedload(ImportRun.items))
        .filter(ImportRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")
    return run
