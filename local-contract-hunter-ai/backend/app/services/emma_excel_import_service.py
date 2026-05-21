from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.scrapers.emma_scraper import public_solicitations_url
from app.services.score_persistence import score_and_store_opportunity
from app.services.source_service import load_business_profile

EMMA_SOURCE_NAME = "Maryland eMMA"
EMMA_SOURCE_URL = "https://emma.maryland.gov/"
EXCEL_EPOCH = datetime(1899, 12, 30)
REQUIRED_HEADERS = {
    "ID",
    "Title",
    "Status",
    "Due / Close Date",
    "Main Category",
    "Solicitation Type",
    "Issuing Agency",
}


def excel_serial_to_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return (EXCEL_EPOCH + timedelta(days=float(value))).date()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return (EXCEL_EPOCH + timedelta(days=float(stripped))).date()
        except ValueError:
            for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(stripped.split()[0], fmt).date()
                except ValueError:
                    continue
    return None


def build_emma_opportunity_url(bpm_id: str) -> str:
    digits = "".join(ch for ch in bpm_id if ch.isdigit())
    opportunity_id = str(int(digits)) if digits else bpm_id
    return f"https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/{opportunity_id}"


def _normalize_header(value: Any) -> str:
    return " ".join(str(value or "").split())


def _description(row: dict[str, Any], publish_date: date | None) -> str:
    parts = [
        f"Status: {row.get('Status')}",
        f"Category: {row.get('Main Category')}",
        f"Type: {row.get('Solicitation Type')}",
    ]
    if publish_date:
        parts.append(f"Published: {publish_date.isoformat()}")
    return " | ".join(part for part in parts if part and not part.endswith(": None"))


def _confidence(row: dict[str, Any]) -> float:
    required_values = [
        row.get("ID"),
        row.get("Title"),
        row.get("Issuing Agency"),
        row.get("Due / Close Date"),
    ]
    present = sum(1 for value in required_values if value not in (None, ""))
    return 0.95 if present == len(required_values) else 0.75


def parse_emma_excel(path: str | Path) -> list[dict]:
    workbook_path = Path(path)
    if not workbook_path.exists():
        raise ValueError(f"Excel file not found: {workbook_path}")
    if workbook_path.suffix.lower() != ".xlsx":
        raise ValueError("eMMA import requires a .xlsx file")

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook.active
    # eMMA exports can report a stale worksheet dimension of A1, so force
    # openpyxl to stream the actual rows.
    sheet.reset_dimensions()
    rows = sheet.iter_rows(values_only=True)
    try:
        headers = [_normalize_header(value) for value in next(rows)]
    except StopIteration as exc:
        raise ValueError("eMMA workbook is empty") from exc

    missing = REQUIRED_HEADERS.difference(headers)
    if missing:
        raise ValueError(f"eMMA workbook is missing required columns: {sorted(missing)}")

    parsed: list[dict] = []
    for raw_values in rows:
        row = dict(zip(headers, raw_values, strict=False))
        status = str(row.get("Status") or "").strip().lower()
        title = str(row.get("Title") or "").strip()
        bpm_id = str(row.get("ID") or "").strip()
        if not title or not bpm_id or status != "open":
            continue

        due_date = excel_serial_to_date(row.get("Due / Close Date"))
        publish_date = excel_serial_to_date(row.get("Publish Date UTC-4"))
        agency = str(row.get("Issuing Agency") or EMMA_SOURCE_NAME).strip()
        parsed.append(
            {
                "title": f"{bpm_id} {title}"[:500],
                "agency": agency,
                "source_name": EMMA_SOURCE_NAME,
                "source_url": public_solicitations_url(EMMA_SOURCE_URL),
                "opportunity_url": build_emma_opportunity_url(bpm_id),
                "due_date": due_date,
                "description_snippet": _description(row, publish_date),
                "extraction_confidence": _confidence(row),
                "manual_review_needed": False,
            }
        )
    workbook.close()
    return parsed


def _is_duplicate(db: Session, item: dict) -> bool:
    return (
        db.query(Opportunity)
        .filter(
            or_(
                Opportunity.opportunity_url == item.get("opportunity_url"),
                and_(
                    Opportunity.title == item.get("title"),
                    Opportunity.agency == item.get("agency"),
                    Opportunity.due_date == item.get("due_date"),
                ),
            )
        )
        .first()
        is not None
    )


def _create_opportunity(db: Session, item: dict) -> Opportunity:
    row = Opportunity(
        title=item["title"],
        agency=item["agency"],
        source_name=item["source_name"],
        source_url=item["source_url"],
        opportunity_url=item.get("opportunity_url"),
        due_date=item.get("due_date"),
        description_snippet=item.get("description_snippet"),
        extraction_confidence=item.get("extraction_confidence", 0.75),
        manual_review_needed=item.get("manual_review_needed", False),
        status="Saved",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def import_emma_excel(
    db: Session,
    path: str | Path,
    profile: dict | None = None,
    auto_score: bool = True,
) -> dict:
    profile = profile if profile is not None else load_business_profile()
    candidates = parse_emma_excel(path)
    created = 0
    duplicates_skipped = 0
    scored = 0

    for item in candidates:
        if _is_duplicate(db, item):
            duplicates_skipped += 1
            continue
        row = _create_opportunity(db, item)
        created += 1
        if auto_score:
            score_and_store_opportunity(db, row, profile)
            scored += 1

    return {
        "ok": True,
        "source": EMMA_SOURCE_NAME,
        "rows_seen": len(candidates),
        "created": created,
        "duplicates_skipped": duplicates_skipped,
        "scored": scored,
        "mock_fallback_used": False,
    }
