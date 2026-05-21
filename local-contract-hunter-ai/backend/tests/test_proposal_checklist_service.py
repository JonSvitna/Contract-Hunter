from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.routes import opportunities as opportunity_routes
from app.services.proposal_checklist_service import build_proposal_checklist


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(opportunity_routes.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def add_opportunity(
    db_session,
    *,
    recommendation: str | None = "Pursue",
    fit_score: int = 86,
    deadline_risk: int = 20,
    complexity_risk: int = 25,
    due_date: date | None = date(2099, 1, 15),
    manual_review_needed: bool = False,
) -> Opportunity:
    opportunity = Opportunity(
        title="Cybersecurity Risk Assessment",
        agency="Test County",
        source_name="Local Procurement",
        source_url="https://example.com/source",
        opportunity_url="https://example.com/opportunity",
        due_date=due_date,
        description_snippet="NIST cybersecurity risk assessment and policy review.",
        extraction_confidence=0.9,
        manual_review_needed=manual_review_needed,
        status="Saved",
    )
    db_session.add(opportunity)
    db_session.flush()

    if recommendation is not None:
        db_session.add(
            OpportunityScore(
                opportunity_id=opportunity.id,
                fit_score=fit_score,
                skill_match=85,
                solo_fit=80,
                revenue_fit=70,
                local_fit=85,
                deadline_risk=deadline_risk,
                complexity_risk=complexity_risk,
                past_performance_risk="Low",
                recommendation=recommendation,
                reasoning=f"{recommendation} candidate",
                next_steps='["Open original posting.", "Confirm submission portal."]',
            )
        )

    db_session.commit()
    db_session.refresh(opportunity)
    return opportunity


def test_checklist_recommends_bid_for_pursue_opportunity(db_session):
    opportunity = add_opportunity(db_session, recommendation="Pursue")

    checklist = build_proposal_checklist(opportunity)

    assert checklist.bid_recommendation == "Bid"
    assert checklist.risk_flags == []
    assert checklist.next_actions[:2] == ["Open original posting.", "Confirm submission portal."]
    assert any("scope" in item.lower() for item in checklist.checklist_items)


def test_checklist_recommends_watch_for_watch_opportunity(db_session):
    opportunity = add_opportunity(db_session, recommendation="Watch", fit_score=62, complexity_risk=45)

    checklist = build_proposal_checklist(opportunity)

    assert checklist.bid_recommendation == "Watch"
    assert "Watch candidate" in checklist.rationale


def test_checklist_recommends_no_bid_for_tight_deadline_and_high_complexity(db_session):
    opportunity = add_opportunity(
        db_session,
        recommendation="Pursue",
        deadline_risk=90,
        complexity_risk=85,
    )

    checklist = build_proposal_checklist(opportunity)

    assert checklist.bid_recommendation == "No Bid"
    assert "Tight deadline risk." in checklist.risk_flags
    assert "High complexity risk for a solo consultancy." in checklist.risk_flags


def test_checklist_requires_manual_review_when_score_missing_and_source_needs_review(db_session):
    opportunity = add_opportunity(
        db_session,
        recommendation=None,
        manual_review_needed=True,
    )

    checklist = build_proposal_checklist(opportunity)

    assert checklist.bid_recommendation == "Manual Review"
    assert "Score missing; run scoring before deciding." in checklist.risk_flags
    assert "Source extraction requires manual review." in checklist.risk_flags


def test_checklist_flags_missing_due_date(db_session):
    opportunity = add_opportunity(db_session, recommendation="Pursue", due_date=None)

    checklist = build_proposal_checklist(opportunity)

    assert checklist.bid_recommendation == "Manual Review"
    assert "Due date is missing; verify closing date before bidding." in checklist.risk_flags


def test_checklist_route_returns_read_only_payload(db_session):
    opportunity = add_opportunity(db_session, recommendation="Pursue")

    response = make_client(db_session).get(f"/api/opportunities/{opportunity.id}/checklist")

    assert response.status_code == 200
    payload = response.json()
    assert payload["opportunity_id"] == opportunity.id
    assert payload["bid_recommendation"] == "Bid"
    assert "checklist_items" in payload
