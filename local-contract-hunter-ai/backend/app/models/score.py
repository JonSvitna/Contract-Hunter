from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), unique=True
    )
    fit_score: Mapped[int] = mapped_column(Integer, default=0)
    skill_match: Mapped[int] = mapped_column(Integer, default=0)
    solo_fit: Mapped[int] = mapped_column(Integer, default=0)
    revenue_fit: Mapped[int] = mapped_column(Integer, default=0)
    local_fit: Mapped[int] = mapped_column(Integer, default=0)
    deadline_risk: Mapped[int] = mapped_column(Integer, default=0)
    complexity_risk: Mapped[int] = mapped_column(Integer, default=0)
    past_performance_risk: Mapped[str] = mapped_column(String(20), default="Medium")
    recommendation: Mapped[str] = mapped_column(String(30), default="Manual Review")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    next_steps: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    opportunity = relationship("Opportunity", back_populates="score")
