from __future__ import annotations

from pydantic import BaseModel


class EmmaExcelImportRequest(BaseModel):
    path: str
    auto_score: bool = True
