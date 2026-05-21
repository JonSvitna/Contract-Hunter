from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.source import Source
from app.models.source_run import SourceRun
from app.routes import sources


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(sources.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_sync_default_sources_route_inserts_missing_sources_and_is_idempotent(db_session):
    db_session.add(
        Source(
            name="Howard County Procurement",
            url="https://custom.example.com/howard",
            source_type="generic",
            active=False,
            search_delay_seconds=4.0,
            notes="Keep my edit",
        )
    )
    db_session.commit()

    first = make_client(db_session).post("/api/sources/sync-defaults")
    second = make_client(db_session).post("/api/sources/sync-defaults")
    howard = db_session.query(Source).filter(Source.name == "Howard County Procurement").one()

    assert first.status_code == 200
    assert first.json()["created"] > 0
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert howard.url == "https://custom.example.com/howard"
    assert howard.active is False


def test_source_dashboard_returns_latest_run_and_never_run_sources(db_session):
    ran = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    never = Source(
        name="Baltimore County Procurement",
        url="https://example.com/baltimore",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add_all([ran, never])
    db_session.commit()
    db_session.add_all(
        [
            SourceRun(
                source_id=ran.id,
                source_name=ran.name,
                source_type=ran.source_type,
                source_url=ran.url,
                run_kind="validation",
                status="failed",
                candidates_found=0,
                error_message="old failure",
            ),
            SourceRun(
                source_id=ran.id,
                source_name=ran.name,
                source_type=ran.source_type,
                source_url=ran.url,
                run_kind="validation",
                status="completed",
                candidates_found=2,
                created=1,
                duplicates_skipped=1,
                scored=1,
                manual_review_candidates=1,
                manual_review_created=1,
            ),
        ]
    )
    db_session.commit()

    response = make_client(db_session).get("/api/sources/dashboard")

    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert items["Howard County Procurement"]["last_run"]["status"] == "completed"
    assert items["Howard County Procurement"]["last_run"]["manual_review_fallback_rate"] == 0.5
    assert items["Baltimore County Procurement"]["last_run"] is None


def test_source_run_history_is_newest_first_and_respects_limit(db_session):
    source = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()
    db_session.add_all(
        [
            SourceRun(
                source_id=source.id,
                source_name=source.name,
                source_type=source.source_type,
                source_url=source.url,
                run_kind="validation",
                status="completed",
                candidates_found=1,
            ),
            SourceRun(
                source_id=source.id,
                source_name=source.name,
                source_type=source.source_type,
                source_url=source.url,
                run_kind="validation",
                status="failed",
                candidates_found=0,
                error_message="new failure",
            ),
        ]
    )
    db_session.commit()

    response = make_client(db_session).get(f"/api/sources/{source.id}/runs?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "failed"
    assert payload[0]["error_message"] == "new failure"
