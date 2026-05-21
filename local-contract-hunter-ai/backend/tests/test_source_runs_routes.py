from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.source import Source
from app.models.source_run import SourceRun, SourceRunItem
from app.routes import source_runs


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(source_runs.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_source_run_detail_returns_items(db_session):
    source = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()
    run = SourceRun(
        source_id=source.id,
        source_name=source.name,
        source_type=source.source_type,
        source_url=source.url,
        run_kind="validation",
        status="completed",
        candidates_found=1,
        created=1,
    )
    db_session.add(run)
    db_session.commit()
    db_session.add(
        SourceRunItem(
            source_run_id=run.id,
            action="created",
            title="Cybersecurity Assessment",
            agency="Howard County Procurement",
            opportunity_url="https://example.com/howard/bids/1",
            extraction_confidence=0.8,
            manual_review_needed=False,
        )
    )
    db_session.commit()

    response = make_client(db_session).get(f"/api/source-runs/{run.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == run.id
    assert payload["manual_review_fallback_rate"] == 0.0
    assert payload["items"][0]["action"] == "created"
    assert payload["items"][0]["title"] == "Cybersecurity Assessment"


def test_source_run_detail_returns_404_for_missing_run(db_session):
    response = make_client(db_session).get("/api/source-runs/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source run not found"
