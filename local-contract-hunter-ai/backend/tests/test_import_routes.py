from __future__ import annotations

from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.database import get_db
from app.models.import_run import ImportRun
from app.routes import imports as import_routes


HEADERS = [
    "ID",
    "Title",
    "Status",
    "Due / Close Date",
    "Publish Date UTC-4",
    "Main Category",
    "Solicitation Type",
    "Issuing Agency",
    "Bid Holders List",
    "eMM ID",
]


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(import_routes.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def workbook_payload() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append(
        [
            "BPM056393",
            "Cyber Asset Attack Surface Management",
            "Open",
            46168.75,
            46162.73311061342,
            "Cloud-based protection or security software",
            "IFB: Invitation for Bid (w/ Min Quals)",
            "DoIT - Dept Of Information Technology - Administration",
            "",
            "",
        ]
    )
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_upload_emma_excel_route_imports_workbook(db_session):
    response = make_client(db_session).post(
        "/api/import/emma-excel/upload",
        files={
            "file": (
                "Public_Solicitations.xlsx",
                workbook_payload(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"auto_score": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["created"] == 1
    assert payload["updated"] == 0
    assert payload["unchanged"] == 0
    assert payload["import_run_id"] == db_session.query(ImportRun).one().id


def test_upload_emma_excel_route_rejects_non_xlsx(db_session):
    response = make_client(db_session).post(
        "/api/import/emma-excel/upload",
        files={"file": ("notes.txt", b"not excel", "text/plain")},
    )

    assert response.status_code == 400
    assert ".xlsx" in response.json()["detail"]


def test_import_history_routes_return_runs_and_items(db_session):
    client = make_client(db_session)
    upload = client.post(
        "/api/import/emma-excel/upload",
        files={
            "file": (
                "Public_Solicitations.xlsx",
                workbook_payload(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    run_id = upload.json()["import_run_id"]

    list_response = client.get("/api/import/runs")
    detail_response = client.get(f"/api/import/runs/{run_id}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run_id
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run_id
    assert detail_response.json()["items"][0]["action"] == "created"
