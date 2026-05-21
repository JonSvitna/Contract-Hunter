from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.models.opportunity import Opportunity
from app.services.emma_excel_import_service import (
    build_emma_opportunity_url,
    excel_serial_to_date,
    import_emma_excel,
    parse_emma_excel,
)


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


def write_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
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
    sheet.append(
        [
            "BPM000001",
            "Closed Road Salt Supplies",
            "Closed",
            46168.75,
            46162.73311061342,
            "Road salt",
            "IFB: Invitation for Bid",
            "Department Of General Services",
            "",
            "",
        ]
    )
    workbook.save(path)


def test_excel_serial_to_date_converts_emma_export_number():
    assert excel_serial_to_date(46168.75).isoformat() == "2026-05-26"


def test_build_emma_opportunity_url_uses_bpm_numeric_id():
    assert build_emma_opportunity_url("BPM056393") == (
        "https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/56393"
    )


def test_parse_emma_excel_normalizes_open_rows(tmp_path):
    workbook_path = tmp_path / "Public_Solicitations.xlsx"
    write_workbook(workbook_path)

    rows = parse_emma_excel(workbook_path)

    assert len(rows) == 1
    assert rows[0]["title"] == "BPM056393 Cyber Asset Attack Surface Management"
    assert rows[0]["agency"] == "DoIT - Dept Of Information Technology - Administration"
    assert rows[0]["due_date"].isoformat() == "2026-05-26"
    assert rows[0]["manual_review_needed"] is False
    assert "Cloud-based protection or security software" in rows[0]["description_snippet"]


def test_import_emma_excel_creates_scores_and_skips_duplicates(db_session, tmp_path):
    workbook_path = tmp_path / "Public_Solicitations.xlsx"
    write_workbook(workbook_path)

    first = import_emma_excel(db_session, workbook_path, profile={"name": "Sean"})
    second = import_emma_excel(db_session, workbook_path, profile={"name": "Sean"})

    row = db_session.query(Opportunity).one()
    assert first["created"] == 1
    assert first["duplicates_skipped"] == 0
    assert first["scored"] == 1
    assert second["created"] == 0
    assert second["duplicates_skipped"] == 1
    assert row.source_name == "Maryland eMMA"
    assert row.score is not None
