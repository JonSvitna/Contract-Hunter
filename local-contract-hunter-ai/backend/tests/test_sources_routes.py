from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.source import Source
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
