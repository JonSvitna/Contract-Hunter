from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from app.models.import_run import ImportRun, ImportRunItem
from app.models.opportunity import Opportunity
from app.services.emma_excel_import_service import (
    build_emma_opportunity_url,
    excel_serial_to_date,
    import_emma_excel,
    import_emma_excel_upload,
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


def workbook_bytes(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def emma_row(
    bpm_id: str = "BPM056393",
    title: str = "Cyber Asset Attack Surface Management",
    status: str = "Open",
    due_date=46168.75,
    agency: str = "DoIT - Dept Of Information Technology - Administration",
) -> list:
    return [
        bpm_id,
        title,
        status,
        due_date,
        46162.73311061342,
        "Cloud-based protection or security software",
        "IFB: Invitation for Bid (w/ Min Quals)",
        agency,
        "",
        "",
    ]


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

    assert len(rows) == 2
    assert rows[0]["external_id"] == "BPM056393"
    assert rows[0]["source_status"] == "Open"
    assert rows[0]["title"] == "BPM056393 Cyber Asset Attack Surface Management"
    assert rows[0]["agency"] == "DoIT - Dept Of Information Technology - Administration"
    assert rows[0]["due_date"].isoformat() == "2026-05-26"
    assert rows[0]["manual_review_needed"] is False
    assert "Cloud-based protection or security software" in rows[0]["description_snippet"]
    assert rows[1]["external_id"] == "BPM000001"
    assert rows[1]["source_status"] == "Closed"


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


def test_import_emma_excel_upload_creates_import_run_items_and_external_id(db_session):
    payload = workbook_bytes([emma_row()])

    result = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        profile={"name": "Sean"},
    )

    row = db_session.query(Opportunity).one()
    run = db_session.query(ImportRun).one()
    item = db_session.query(ImportRunItem).one()
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["unchanged"] == 0
    assert result["skipped"] == 0
    assert result["scored"] == 1
    assert row.external_id == "BPM056393"
    assert row.source_status == "Open"
    assert row.last_seen_at is not None
    assert row.status == "Saved"
    assert row.score is not None
    assert run.filename == "Public_Solicitations.xlsx"
    assert run.workbook_bytes == payload
    assert item.action == "created"
    assert item.opportunity_id == row.id
    assert item.external_id == "BPM056393"
    assert item.row_sha256


def test_import_emma_excel_upload_reupload_marks_unchanged(db_session):
    payload = workbook_bytes([emma_row()])

    first = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )
    second = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["unchanged"] == 1
    assert db_session.query(Opportunity).count() == 1
    assert db_session.query(ImportRun).count() == 2
    assert (
        db_session.query(ImportRunItem)
        .order_by(ImportRunItem.id.desc())
        .first()
        .action
        == "unchanged"
    )


def test_import_emma_excel_upload_skips_duplicate_ids_within_same_workbook(db_session):
    payload = workbook_bytes(
        [
            emma_row(),
            emma_row(title="Duplicate Row Should Not Update Same Import"),
        ]
    )

    first = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )
    second = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )

    row = db_session.query(Opportunity).one()
    actions = [item.action for item in db_session.query(ImportRunItem).order_by(ImportRunItem.id).all()]
    assert first["created"] == 1
    assert first["updated"] == 0
    assert first["skipped"] == 1
    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 1
    assert second["skipped"] == 1
    assert row.title == "BPM056393 Cyber Asset Attack Surface Management"
    assert actions == ["created", "skipped", "unchanged", "skipped"]


def test_import_emma_excel_upload_updates_source_fields_and_preserves_status(db_session):
    first_payload = workbook_bytes([emma_row()])
    changed_payload = workbook_bytes(
        [
            emma_row(
                title="Cyber Asset Attack Surface Management Updated",
                status="Closed",
                due_date=46169.75,
            )
        ]
    )

    import_emma_excel_upload(
        db_session,
        first_payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )
    row = db_session.query(Opportunity).one()
    original_score_id = row.score.id
    row.status = "Pursue"
    db_session.commit()

    result = import_emma_excel_upload(
        db_session,
        changed_payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )

    db_session.refresh(row)
    assert result["created"] == 0
    assert result["updated"] == 1
    assert result["scored"] == 0
    assert row.title == "BPM056393 Cyber Asset Attack Surface Management Updated"
    assert row.due_date.isoformat() == "2026-05-27"
    assert row.source_status == "Closed"
    assert row.status == "Pursue"
    assert row.score.id == original_score_id
    assert (
        db_session.query(ImportRunItem)
        .order_by(ImportRunItem.id.desc())
        .first()
        .action
        == "updated"
    )


def test_import_emma_excel_upload_skips_closed_new_rows(db_session):
    payload = workbook_bytes([emma_row(status="Closed")])

    result = import_emma_excel_upload(
        db_session,
        payload,
        filename="Public_Solicitations.xlsx",
        profile={"name": "Sean"},
    )

    assert result["created"] == 0
    assert result["skipped"] == 1
    assert db_session.query(Opportunity).count() == 0
    item = db_session.query(ImportRunItem).one()
    assert item.action == "skipped"
    assert "not open" in (item.change_summary or "")
