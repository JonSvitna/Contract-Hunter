from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.routes import opportunities


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(opportunities.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def add_opportunity(
    db_session,
    title: str,
    agency: str = "Maryland Department of Test",
    status: str = "Saved",
    source_name: str = "Maryland eMMA",
    source_status: str = "Open",
    external_id: str | None = None,
    due_date: date | None = None,
    confidence: float = 0.9,
    manual_review: bool = False,
    recommendation: str | None = None,
    fit_score: int = 0,
    skill_match: int = 0,
    created_at: datetime | None = None,
):
    stamp = created_at or datetime.utcnow()
    row = Opportunity(
        title=title,
        agency=agency,
        source_name=source_name,
        source_url="https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public",
        external_id=external_id,
        source_status=source_status,
        due_date=due_date,
        description_snippet=f"{title} description",
        status=status,
        extraction_confidence=confidence,
        manual_review_needed=manual_review,
        created_at=stamp,
        updated_at=stamp,
    )
    db_session.add(row)
    db_session.flush()
    if recommendation:
        db_session.add(
            OpportunityScore(
                opportunity_id=row.id,
                fit_score=fit_score,
                skill_match=skill_match,
                solo_fit=70,
                revenue_fit=70,
                local_fit=80,
                deadline_risk=20,
                complexity_risk=30,
                past_performance_risk="Low",
                recommendation=recommendation,
                reasoning=f"{recommendation} reasoning",
                next_steps='["Review posting"]',
            )
        )
    db_session.commit()
    db_session.refresh(row)
    return row


def test_search_opportunities_paginates_results(db_session):
    base = datetime(2026, 1, 1)
    for idx in range(6):
        add_opportunity(
            db_session,
            title=f"Opportunity {idx}",
            external_id=f"BPM{idx:06d}",
            created_at=base + timedelta(days=idx),
        )

    response = make_client(db_session).get("/api/opportunities/search?page=2&page_size=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert payload["page"] == 2
    assert payload["page_size"] == 5
    assert payload["pages"] == 2
    assert len(payload["items"]) == 1


def test_search_opportunities_filters_text_bpm_status_recommendation_and_source(db_session):
    add_opportunity(
        db_session,
        title="Cyber Risk Assessment",
        external_id="BPM056393",
        status="Pursue",
        source_status="Open",
        recommendation="Pursue",
        fit_score=91,
    )
    add_opportunity(
        db_session,
        title="Road Salt Supplies",
        external_id="BPM000001",
        status="Saved",
        source_status="Closed",
        recommendation="Skip",
        fit_score=12,
    )

    response = make_client(db_session).get(
        "/api/opportunities/search",
        params={
            "q": "cyber",
            "bpm_id": "56393",
            "status": "Pursue",
            "recommendation": "Pursue",
            "source_status": "Open",
            "source": "Maryland eMMA",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["external_id"] == "BPM056393"


def test_search_opportunities_filters_manual_review_agency_dates_and_scores(db_session):
    add_opportunity(
        db_session,
        title="Manual Cyber Assessment",
        agency="Howard County",
        external_id="BPM111111",
        due_date=date(2026, 6, 1),
        confidence=0.95,
        manual_review=True,
        recommendation="Manual Review",
        fit_score=70,
        skill_match=85,
    )
    add_opportunity(
        db_session,
        title="Low Fit Work",
        agency="Baltimore County",
        external_id="BPM222222",
        due_date=date(2026, 8, 1),
        confidence=0.5,
        manual_review=False,
        recommendation="Watch",
        fit_score=50,
        skill_match=55,
    )

    response = make_client(db_session).get(
        "/api/opportunities/search",
        params={
            "manual_review": "true",
            "agency": "Howard",
            "due_from": "2026-05-01",
            "due_to": "2026-07-01",
            "min_confidence": "0.9",
            "min_fit_score": "65",
            "min_skill_match": "80",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["agency"] == "Howard County"


def test_search_opportunities_combined_manual_review_recommendation_includes_scored_and_unscored(db_session):
    add_opportunity(db_session, title="Pursue Work", external_id="BPM1", recommendation="Pursue", fit_score=91)
    add_opportunity(db_session, title="Manual Review Work", external_id="BPM2", recommendation="Manual Review", fit_score=55)
    add_opportunity(db_session, title="Unscored Work", external_id="BPM3")
    add_opportunity(db_session, title="Skip Work", external_id="BPM4", recommendation="Skip", fit_score=20)

    response = make_client(db_session).get(
        "/api/opportunities/search",
        params=[("recommendation", "Pursue"), ("recommendation", "Manual Review")],
    )

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert titles == {"Pursue Work", "Manual Review Work", "Unscored Work"}


def test_search_opportunities_sorts_by_fit_score_desc(db_session):
    add_opportunity(db_session, title="Low Fit", external_id="BPM1", recommendation="Watch", fit_score=40)
    add_opportunity(db_session, title="High Fit", external_id="BPM2", recommendation="Pursue", fit_score=95)

    response = make_client(db_session).get("/api/opportunities/search?sort=fit_score&direction=desc")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["High Fit", "Low Fit"]


def test_opportunity_summary_returns_aggregate_counts(db_session):
    add_opportunity(db_session, title="Pursue Work", status="Saved", recommendation="Pursue", due_date=date(2099, 1, 1))
    add_opportunity(db_session, title="Watch Work", status="Saved", recommendation="Watch", due_date=date(2099, 2, 1))
    add_opportunity(db_session, title="Skipped Work", status="Skipped", recommendation="Skip", due_date=date(2020, 1, 1))
    add_opportunity(db_session, title="Unscored Work", status="Saved", manual_review=True)

    response = make_client(db_session).get("/api/opportunities/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["pursue"] == 1
    assert payload["watch"] == 1
    assert payload["skipped"] == 1
    assert payload["manual_review"] >= 1
    assert payload["upcoming_deadlines"] == 2


def test_search_opportunities_rejects_invalid_sort_and_keeps_raw_list_compatible(db_session):
    add_opportunity(db_session, title="Raw List")

    bad = make_client(db_session).get("/api/opportunities/search?sort=unknown")
    raw = make_client(db_session).get("/api/opportunities")

    assert bad.status_code == 400
    assert raw.status_code == 200
    assert isinstance(raw.json(), list)
    assert raw.json()[0]["title"] == "Raw List"
