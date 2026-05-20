from __future__ import annotations

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    name: str
    url: str
    source_type: str = "generic"
    active: bool = True
    search_delay_seconds: float = Field(default=2.0, ge=0.5)
    notes: str | None = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    source_type: str | None = None
    active: bool | None = None
    search_delay_seconds: float | None = Field(default=None, ge=0.5)
    notes: str | None = None


class SourceRead(SourceBase):
    id: int

    class Config:
        from_attributes = True
