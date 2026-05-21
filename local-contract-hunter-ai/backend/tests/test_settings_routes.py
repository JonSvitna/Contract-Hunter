from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.routes import search as search_routes


def make_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "config_dir", tmp_path)
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api")
    return TestClient(app)


def test_patch_keywords_normalizes_and_persists(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.patch(
        "/api/search/config/keywords",
        json={"keywords": [" cybersecurity ", "", "Cybersecurity", "NIST"]},
    )

    assert response.status_code == 200
    assert response.json() == {"keywords": ["cybersecurity", "NIST"]}

    preview = client.get("/api/search/config")
    assert preview.status_code == 200
    assert preview.json()["keywords"] == ["cybersecurity", "NIST"]
    assert "scoring_rules" in preview.json()


def test_patch_business_profile_persists_valid_profile(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    payload = {
        "name": "Sean",
        "company": "Vulnaguard LLC",
        "location": "Maryland",
        "profile": "Solo consultant",
        "skills": ["risk assessment"],
        "certifications": ["Security+"],
        "education": [],
        "target_contract_size": {
            "preferred_min": 2000,
            "preferred_max": 25000,
            "acceptable_max": 50000,
        },
        "preferred_work": ["vulnerability assessment"],
        "avoid": ["24/7 SOC"],
    }

    response = client.patch("/api/search/config/business-profile", json=payload)

    assert response.status_code == 200
    assert response.json()["company"] == "Vulnaguard LLC"
    assert client.get("/api/search/config").json()["business_profile"]["skills"] == ["risk assessment"]


def test_patch_business_profile_rejects_invalid_contract_size(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    payload = {
        "name": "Sean",
        "company": "Vulnaguard LLC",
        "location": "Maryland",
        "profile": "Solo consultant",
        "skills": ["risk assessment"],
        "certifications": [],
        "education": [],
        "target_contract_size": {
            "preferred_min": 25000,
            "preferred_max": 2000,
            "acceptable_max": 50000,
        },
        "preferred_work": [],
        "avoid": [],
    }

    response = client.patch("/api/search/config/business-profile", json=payload)

    assert response.status_code == 422


def valid_scoring_rules() -> dict:
    return {
        "weights": {
            "skill_match": 0.25,
            "solo_fit": 0.25,
            "revenue_fit": 0.2,
            "local_fit": 0.3,
        },
        "penalties": {"complexity_factor": 0.2},
        "hard_penalties": ["staffing"],
        "positive_skills": ["cybersecurity"],
        "recommendation_bands": {"pursue_min": 75, "watch_min": 55},
        "deadline_rules": {"expired": 100, "lt_3_days": 90, "lt_7_days": 65},
    }


def test_patch_scoring_rules_persists_valid_rules(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.patch("/api/search/config/scoring-rules", json=valid_scoring_rules())

    assert response.status_code == 200
    assert response.json()["positive_skills"] == ["cybersecurity"]
    assert client.get("/api/search/config").json()["scoring_rules"]["recommendation_bands"]["pursue_min"] == 75


def test_patch_scoring_rules_rejects_out_of_bounds_weight(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    payload = valid_scoring_rules()
    payload["weights"]["skill_match"] = 1.5

    response = client.patch("/api/search/config/scoring-rules", json=payload)

    assert response.status_code == 422
