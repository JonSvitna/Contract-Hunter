from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from app.models.opportunity import Opportunity


DIGEST_LIMIT = 5
WATCH_MIN_FIT_SCORE = 55
ELIGIBLE_RECOMMENDATIONS = {"Pursue", "Watch"}


@dataclass(frozen=True)
class DigestCandidate:
    id: int
    title: str
    agency: str
    source_name: str
    opportunity_url: str | None
    due_date: date | None
    status: str
    fit_score: int
    recommendation: str
    reasoning: str


def _is_candidate(opportunity: Opportunity) -> bool:
    if opportunity.status == "Skipped":
        return False
    if not opportunity.score:
        return False
    if opportunity.score.recommendation not in ELIGIBLE_RECOMMENDATIONS:
        return False
    # MVP threshold mirrors the Watch cutoff used by scoring_service._recommendation.
    return opportunity.score.fit_score >= WATCH_MIN_FIT_SCORE


def _sort_key(candidate: DigestCandidate) -> tuple[int, int, date, int]:
    recommendation_rank = 0 if candidate.recommendation == "Pursue" else 1
    due_date = candidate.due_date or date.max
    return (recommendation_rank, -candidate.fit_score, due_date, candidate.id)


def select_digest_candidates(
    opportunities: Iterable[Opportunity],
    *,
    limit: int = DIGEST_LIMIT,
) -> list[DigestCandidate]:
    seen_ids: set[int] = set()
    candidates: list[DigestCandidate] = []
    for opportunity in opportunities:
        if opportunity.id in seen_ids:
            continue
        seen_ids.add(opportunity.id)
        if not _is_candidate(opportunity):
            continue
        candidates.append(
            DigestCandidate(
                id=opportunity.id,
                title=opportunity.title,
                agency=opportunity.agency,
                source_name=opportunity.source_name,
                opportunity_url=opportunity.opportunity_url,
                due_date=opportunity.due_date,
                status=opportunity.status,
                fit_score=opportunity.score.fit_score,
                recommendation=opportunity.score.recommendation,
                reasoning=opportunity.score.reasoning,
            )
        )

    return sorted(candidates, key=_sort_key)[:limit]
