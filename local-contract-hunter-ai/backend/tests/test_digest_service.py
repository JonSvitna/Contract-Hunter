from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.routes import digest as digest_routes
from app.services.digest_service import select_digest_candidates


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(digest_routes.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def add_opportunity(
    db_session,
    *,
    title: str,
    status: str = "Saved",
    recommendation: str | None = "Watch",
    fit_score: int | None = 65,
    due_date: date | None = date(2099, 1, 15),
) -> Opportunity:
    opportunity = Opportunity(
        title=title,
        agency="Test County",
        source_name="Local Procurement",
        source_url="https://example.com",
        opportunity_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        due_date=due_date,
        description_snippet="Cybersecurity risk assessment.",
        extraction_confidence=0.9,
        manual_review_needed=False,
        status=status,
    )
    db_session.add(opportunity)
    db_session.flush()
    if recommendation is not None and fit_score is not None:
        db_session.add(
            OpportunityScore(
                opportunity_id=opportunity.id,
                fit_score=fit_score,
                skill_match=80,
                solo_fit=75,
                revenue_fit=70,
                local_fit=85,
                deadline_risk=20,
                complexity_risk=30,
                past_performance_risk="Low",
                recommendation=recommendation,
                reasoning=f"{recommendation} candidate",
                next_steps="[]",
            )
        )
    db_session.commit()
    db_session.refresh(opportunity)
    return opportunity


def test_select_digest_candidates_orders_pursue_before_watch_then_fit_score(db_session):
    add_opportunity(db_session, title="Watch high score", recommendation="Watch", fit_score=96)
    pursue_mid = add_opportunity(db_session, title="Pursue mid score", recommendation="Pursue", fit_score=76)
    pursue_high = add_opportunity(db_session, title="Pursue high score", recommendation="Pursue", fit_score=91)
    watch_mid = add_opportunity(db_session, title="Watch mid score", recommendation="Watch", fit_score=64)

    candidates = select_digest_candidates(db_session.query(Opportunity).all(), limit=10)

    assert [candidate.id for candidate in candidates] == [
        pursue_high.id,
        pursue_mid.id,
        db_session.query(Opportunity).filter_by(title="Watch high score").one().id,
        watch_mid.id,
    ]


def test_select_digest_candidates_excludes_skipped_and_unscored_handles_missing_due_date(db_session):
    kept = add_opportunity(
        db_session,
        title="No due date pursue",
        recommendation="Pursue",
        fit_score=82,
        due_date=None,
    )
    add_opportunity(db_session, title="Skipped pursue", status="Skipped", recommendation="Pursue", fit_score=95)
    add_opportunity(db_session, title="Unscored saved", recommendation=None, fit_score=None)

    candidates = select_digest_candidates(db_session.query(Opportunity).all(), limit=10)

    assert len(candidates) == 1
    assert candidates[0].id == kept.id
    assert candidates[0].due_date is None


def test_select_digest_candidates_deduplicates_by_opportunity_id(db_session):
    opportunity = add_opportunity(db_session, title="Duplicate candidate", recommendation="Pursue", fit_score=88)

    candidates = select_digest_candidates([opportunity, opportunity], limit=10)

    assert [candidate.id for candidate in candidates] == [opportunity.id]


def test_digest_preview_route_returns_generated_at_and_candidates(db_session):
    expected = add_opportunity(db_session, title="Preview pursue", recommendation="Pursue", fit_score=89)
    add_opportunity(db_session, title="Preview skipped", status="Skipped", recommendation="Pursue", fit_score=97)

    response = make_client(db_session).get("/api/digest/preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"]
    assert [candidate["id"] for candidate in payload["candidates"]] == [expected.id]
    assert payload["candidates"][0]["due_date"] == "2099-01-15"
