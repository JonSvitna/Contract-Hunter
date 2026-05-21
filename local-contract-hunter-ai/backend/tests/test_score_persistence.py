from __future__ import annotations

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.services.score_persistence import score_and_store_opportunity


def test_score_and_store_creates_score(db_session):
    opportunity = Opportunity(
        title="Cybersecurity Vulnerability Assessment",
        agency="Maryland eMMA",
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/123",
        description_snippet="NIST risk assessment and vulnerability scanning support.",
        extraction_confidence=0.85,
        manual_review_needed=False,
        status="Saved",
    )
    db_session.add(opportunity)
    db_session.commit()
    db_session.refresh(opportunity)

    payload = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})

    stored = db_session.query(OpportunityScore).filter_by(opportunity_id=opportunity.id).one()
    assert payload["recommendation"] in {"Pursue", "Watch", "Skip", "Manual Review"}
    assert stored.opportunity_id == opportunity.id
    assert stored.fit_score == payload["fit_score"]
    assert stored.next_steps.startswith("[")


def test_score_and_store_updates_existing_score(db_session):
    opportunity = Opportunity(
        title="Cybersecurity Policy Review",
        agency="Maryland eMMA",
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/456",
        description_snippet="Compliance documentation and NIST policy review.",
        extraction_confidence=0.8,
        manual_review_needed=False,
        status="Saved",
    )
    db_session.add(opportunity)
    db_session.commit()
    db_session.refresh(opportunity)

    first = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})
    opportunity.description_snippet = "24/7 SOC monitoring and managed services."
    second = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})

    stored_rows = db_session.query(OpportunityScore).filter_by(opportunity_id=opportunity.id).all()
    assert len(stored_rows) == 1
    assert second["fit_score"] <= first["fit_score"]
