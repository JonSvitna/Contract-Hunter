from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmmaExcelImportRequest(BaseModel):
    path: str
    auto_score: bool = True


class EmmaExcelImportResult(BaseModel):
    ok: bool
    import_run_id: int | None = None
    source: str
    filename: str | None = None
    rows_seen: int
    created: int
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    duplicates_skipped: int = 0
    scored: int
    mock_fallback_used: bool


class ImportRunItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int | None
    external_id: str | None
    row_sha256: str | None
    action: str
    change_summary: str | None
    raw_title: str | None
    raw_agency: str | None
    raw_due_date: str | None
    raw_source_status: str | None


class ImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    filename: str
    content_type: str | None
    file_size_bytes: int
    file_sha256: str
    uploaded_at: datetime
    rows_seen: int
    created: int
    updated: int
    unchanged: int
    skipped: int
    scored: int
    status: str
    error_message: str | None


class ImportRunDetailRead(ImportRunRead):
    items: list[ImportRunItemRead] = Field(default_factory=list)
