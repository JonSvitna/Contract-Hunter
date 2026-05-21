from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    run_kind: Mapped[str] = mapped_column(String(50), default="manual", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_score: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mock_fallback_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mock_fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manual_review_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manual_review_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items = relationship(
        "SourceRunItem",
        back_populates="source_run",
        cascade="all, delete-orphan",
        order_by="SourceRunItem.id",
    )


class SourceRunItem(Base):
    __tablename__ = "source_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_run_id: Mapped[int] = mapped_column(
        ForeignKey("source_runs.id"), nullable=False, index=True
    )
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opportunity_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_review_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_run = relationship("SourceRun", back_populates="items")
