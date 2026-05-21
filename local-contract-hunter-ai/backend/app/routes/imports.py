from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.imports import EmmaExcelImportRequest
from app.services.emma_excel_import_service import import_emma_excel
from app.services.source_service import load_business_profile

router = APIRouter(prefix="/import", tags=["import"])


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
