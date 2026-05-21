from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.source import Source
from app.routes import search as search_routes


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_validate_source_route_runs_active_generic_source_without_mock_fallback(db_session, monkeypatch):
    source = Source(
        name="Howard County Procurement",
        url="https://example.com/howard",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()
    captured_options = []

    def fake_execute_search(db, options):
        assert db is db_session
        captured_options.append(options)
        return {
            "ok": True,
            "created": 1,
            "duplicates_skipped": 0,
            "sources": 1,
            "profile_name": "Sean",
            "scored": 1,
            "mock_fallback_used": False,
            "diagnostics": [{"source": "Howard County Procurement", "source_type": "generic", "candidates": 1}],
        }

    monkeypatch.setattr(search_routes, "execute_search", fake_execute_search)

    response = make_client(db_session).post(
        "/api/search/validate/source",
        json={"source_name": "Howard County Procurement", "auto_score": True},
    )

    assert response.status_code == 200
    assert response.json()["mock_fallback_used"] is False
    assert len(captured_options) == 1
    assert captured_options[0].source_name == "Howard County Procurement"
    assert captured_options[0].source_type == "generic"
    assert captured_options[0].allow_mock_fallback is False
    assert captured_options[0].auto_score is True


def test_validate_source_route_rejects_non_generic_source(db_session, monkeypatch):
    source = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    def fail_execute_search(db, options):
        raise AssertionError("route should reject before running search")

    monkeypatch.setattr(search_routes, "execute_search", fail_execute_search)

    response = make_client(db_session).post(
        "/api/search/validate/source",
        json={"source_name": "Maryland eMMA"},
    )

    assert response.status_code == 400
    assert "generic local source" in response.json()["detail"]
