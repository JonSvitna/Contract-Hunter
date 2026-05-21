# eMMA Upload Import History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace path-based eMMA Excel imports with browser workbook uploads that save import history, create new opportunities, update changed source fields, and preserve user workflow status.

**Architecture:** Add import run tables and stable source identity fields, then route uploaded workbook bytes through the existing eMMA normalization pipeline. The frontend will send `multipart/form-data` and render import summary/history from the backend API. Because this repo does not use Alembic yet, add a small additive schema bootstrap for existing SQLite/Postgres databases before relying on new columns.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic, openpyxl, pytest, Next.js App Router, React, TypeScript.

---

## File Structure

- Modify `local-contract-hunter-ai/backend/requirements.txt`: add `python-multipart` for FastAPI file uploads.
- Modify `local-contract-hunter-ai/backend/app/models/opportunity.py`: add source identity/freshness columns and import item relationship.
- Create `local-contract-hunter-ai/backend/app/models/import_run.py`: define `ImportRun` and `ImportRunItem`.
- Modify `local-contract-hunter-ai/backend/app/models/__init__.py`: export new models.
- Create `local-contract-hunter-ai/backend/app/services/schema_maintenance.py`: add missing columns for existing deployed databases.
- Modify `local-contract-hunter-ai/backend/app/main.py`: run additive schema maintenance at startup after `create_all`.
- Modify `local-contract-hunter-ai/backend/app/schemas/opportunity.py`: expose source identity/freshness fields in API responses.
- Modify `local-contract-hunter-ai/backend/app/schemas/imports.py`: add upload/history response schemas.
- Modify `local-contract-hunter-ai/backend/app/services/emma_excel_import_service.py`: parse workbook bytes, track row hashes, persist runs/items, create/update opportunities.
- Modify `local-contract-hunter-ai/backend/app/routes/imports.py`: add upload and history endpoints while keeping the path-based endpoint.
- Modify `local-contract-hunter-ai/backend/tests/conftest.py`: import new models so `Base.metadata.create_all()` includes them.
- Modify `local-contract-hunter-ai/backend/tests/test_emma_excel_import_service.py`: cover create, unchanged, update, status preservation, and closed-row skip behavior.
- Create `local-contract-hunter-ai/backend/tests/test_import_routes.py`: cover upload endpoint and history endpoints.
- Modify `local-contract-hunter-ai/frontend/lib/types.ts`: add import run/result fields and optional opportunity source fields.
- Modify `local-contract-hunter-ai/frontend/lib/api.ts`: support JSON requests and multipart upload requests.
- Modify `local-contract-hunter-ai/frontend/components/EmmaExcelImportPanel.tsx`: replace path textbox with file picker and recent history.

Do not create git commits during execution unless the user explicitly requests commits.

---

## Task 1: Backend Dependency, Models, And Runtime Schema Bootstrap

**Files:**
- Modify: `local-contract-hunter-ai/backend/requirements.txt`
- Modify: `local-contract-hunter-ai/backend/app/models/opportunity.py`
- Create: `local-contract-hunter-ai/backend/app/models/import_run.py`
- Modify: `local-contract-hunter-ai/backend/app/models/__init__.py`
- Create: `local-contract-hunter-ai/backend/app/services/schema_maintenance.py`
- Modify: `local-contract-hunter-ai/backend/app/main.py`
- Modify: `local-contract-hunter-ai/backend/app/schemas/opportunity.py`
- Modify: `local-contract-hunter-ai/backend/tests/conftest.py`

- [ ] **Step 1: Add the upload dependency**

Add `python-multipart` to `local-contract-hunter-ai/backend/requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.32.1
SQLAlchemy==2.0.36
psycopg2-binary==2.9.12
pydantic==2.10.3
PyYAML==6.0.2
python-dateutil==2.9.0.post0
playwright==1.49.1
openai==1.58.1
python-multipart
pytest
openpyxl
```

- [ ] **Step 2: Add opportunity source identity fields**

In `local-contract-hunter-ai/backend/app/models/opportunity.py`, update imports and the model:

```python
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
```

Add these columns after `opportunity_url`:

```python
external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
source_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

Add this column after `created_at`:

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime,
    default=datetime.utcnow,
    onupdate=datetime.utcnow,
)
last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

Add this relationship after the existing `score` relationship:

```python
import_items = relationship("ImportRunItem", back_populates="opportunity")
```

- [ ] **Step 3: Add import run models**

Create `local-contract-hunter-ai/backend/app/models/import_run.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workbook_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    rows_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items = relationship(
        "ImportRunItem",
        back_populates="import_run",
        cascade="all, delete-orphan",
        order_by="ImportRunItem.id",
    )


class ImportRunItem(Base):
    __tablename__ = "import_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), nullable=False, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    row_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_due_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_source_status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    import_run = relationship("ImportRun", back_populates="items")
    opportunity = relationship("Opportunity", back_populates="import_items")
```

- [ ] **Step 4: Export and load the new models**

Update `local-contract-hunter-ai/backend/app/models/__init__.py`:

```python
from app.models.import_run import ImportRun, ImportRunItem
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.models.source import Source

__all__ = ["ImportRun", "ImportRunItem", "Opportunity", "OpportunityScore", "Source"]
```

Update `local-contract-hunter-ai/backend/tests/conftest.py` imports:

```python
from app.database import Base  # noqa: E402
from app.models.import_run import ImportRun, ImportRunItem  # noqa: F401,E402
from app.models.opportunity import Opportunity  # noqa: F401,E402
from app.models.score import OpportunityScore  # noqa: F401,E402
from app.models.source import Source  # noqa: F401,E402
```

- [ ] **Step 5: Add additive runtime schema maintenance**

Create `local-contract-hunter-ai/backend/app/services/schema_maintenance.py`:

```python
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


OPPORTUNITY_COLUMNS = {
    "external_id": "VARCHAR(255)",
    "source_status": "VARCHAR(100)",
    "updated_at": "TIMESTAMP",
    "last_seen_at": "TIMESTAMP",
}


def ensure_runtime_schema(engine: Engine) -> None:
    """Apply additive schema changes for deployments without migrations."""
    inspector = inspect(engine)
    if not inspector.has_table("opportunities"):
        return

    existing = {column["name"] for column in inspector.get_columns("opportunities")}
    missing = {
        name: ddl_type
        for name, ddl_type in OPPORTUNITY_COLUMNS.items()
        if name not in existing
    }
    if not missing:
        return

    with engine.begin() as connection:
        for name, ddl_type in missing.items():
            connection.execute(text(f"ALTER TABLE opportunities ADD COLUMN {name} {ddl_type}"))
```

Modify `local-contract-hunter-ai/backend/app/main.py`:

```python
from app.services.schema_maintenance import ensure_runtime_schema
```

Then update startup:

```python
@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    db = SessionLocal()
    try:
        seed_sources_if_empty(db)
    finally:
        db.close()
```

- [ ] **Step 6: Expose new opportunity fields**

Update `local-contract-hunter-ai/backend/app/schemas/opportunity.py`:

```python
from datetime import date, datetime
```

Add fields to `OpportunityRead` after `opportunity_url`:

```python
external_id: str | None = None
source_status: str | None = None
last_seen_at: datetime | None = None
updated_at: datetime | None = None
```

- [ ] **Step 7: Run model-focused tests**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_emma_excel_import_service.py -q
```

Expected before service updates: existing tests may fail because new behavior is not implemented yet. They should not fail with model import errors or table creation errors.

---

## Task 2: Import Service History, Row Hashes, And Update Behavior

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/services/emma_excel_import_service.py`
- Modify: `local-contract-hunter-ai/backend/tests/test_emma_excel_import_service.py`

- [ ] **Step 1: Add failing tests for upload/history behavior**

Append helper functions to `local-contract-hunter-ai/backend/tests/test_emma_excel_import_service.py`:

```python
from io import BytesIO

from app.models.import_run import ImportRun, ImportRunItem
```

Add this workbook builder near `write_workbook`:

```python
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
```

Add tests:

```python
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
```

```python
def test_import_emma_excel_upload_reupload_marks_unchanged(db_session):
    payload = workbook_bytes([emma_row()])

    first = import_emma_excel_upload(db_session, payload, filename="Public_Solicitations.xlsx", profile={"name": "Sean"})
    second = import_emma_excel_upload(db_session, payload, filename="Public_Solicitations.xlsx", profile={"name": "Sean"})

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["unchanged"] == 1
    assert db_session.query(Opportunity).count() == 1
    assert db_session.query(ImportRun).count() == 2
```

```python
def test_import_emma_excel_upload_updates_source_fields_and_preserves_status(db_session):
    first_payload = workbook_bytes([emma_row()])
    changed_payload = workbook_bytes([
        emma_row(
            title="Cyber Asset Attack Surface Management Updated",
            status="Closed",
            due_date=46169.75,
        )
    ])

    import_emma_excel_upload(db_session, first_payload, filename="Public_Solicitations.xlsx", profile={"name": "Sean"})
    row = db_session.query(Opportunity).one()
    row.status = "Pursue"
    db_session.commit()

    result = import_emma_excel_upload(db_session, changed_payload, filename="Public_Solicitations.xlsx", profile={"name": "Sean"})

    db_session.refresh(row)
    assert result["created"] == 0
    assert result["updated"] == 1
    assert row.title == "BPM056393 Cyber Asset Attack Surface Management Updated"
    assert row.due_date.isoformat() == "2026-05-27"
    assert row.source_status == "Closed"
    assert row.status == "Pursue"
    assert db_session.query(ImportRunItem).order_by(ImportRunItem.id.desc()).first().action == "updated"
```

```python
def test_import_emma_excel_upload_skips_closed_new_rows(db_session):
    payload = workbook_bytes([emma_row(status="Closed")])

    result = import_emma_excel_upload(db_session, payload, filename="Public_Solicitations.xlsx", profile={"name": "Sean"})

    assert result["created"] == 0
    assert result["skipped"] == 1
    assert db_session.query(Opportunity).count() == 0
    item = db_session.query(ImportRunItem).one()
    assert item.action == "skipped"
    assert "not open" in (item.change_summary or "")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_emma_excel_import_service.py -q
```

Expected: FAIL with `NameError` or import error for `import_emma_excel_upload`.

- [ ] **Step 3: Refactor parser to preserve source status and external ID**

In `local-contract-hunter-ai/backend/app/services/emma_excel_import_service.py`, add imports:

```python
import hashlib
import json
from io import BytesIO
```

Add model imports:

```python
from app.models.import_run import ImportRun, ImportRunItem
```

Change parsed row output in `parse_emma_excel` so closed rows are not filtered out before history tracking:

```python
status = str(row.get("Status") or "").strip()
title = str(row.get("Title") or "").strip()
bpm_id = str(row.get("ID") or "").strip()
if not title or not bpm_id:
    continue
```

Add fields to the parsed dict:

```python
"external_id": bpm_id,
"source_status": status,
```

- [ ] **Step 4: Add byte parsing and row hash helpers**

Add these functions in `emma_excel_import_service.py`:

```python
def parse_emma_excel_bytes(contents: bytes) -> list[dict]:
    if not contents:
        raise ValueError("Excel file is empty")
    workbook = load_workbook(BytesIO(contents), read_only=True, data_only=True)
    try:
        return _parse_workbook(workbook)
    finally:
        workbook.close()


def _parse_workbook(workbook) -> list[dict]:
    sheet = workbook.active
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
        item = _parse_row(headers, raw_values)
        if item:
            parsed.append(item)
    return parsed


def _row_hash(item: dict) -> str:
    payload = {
        "external_id": item.get("external_id"),
        "title": item.get("title"),
        "agency": item.get("agency"),
        "source_url": item.get("source_url"),
        "opportunity_url": item.get("opportunity_url"),
        "due_date": item.get("due_date").isoformat() if item.get("due_date") else None,
        "description_snippet": item.get("description_snippet"),
        "extraction_confidence": item.get("extraction_confidence"),
        "manual_review_needed": item.get("manual_review_needed"),
        "source_status": item.get("source_status"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

Move the row parsing body from `parse_emma_excel` into `_parse_row(headers, raw_values)`. Keep `parse_emma_excel(path)` as a path wrapper:

```python
def parse_emma_excel(path: str | Path) -> list[dict]:
    workbook_path = Path(path)
    if not workbook_path.exists():
        raise ValueError(f"Excel file not found: {workbook_path}")
    if workbook_path.suffix.lower() != ".xlsx":
        raise ValueError("eMMA import requires a .xlsx file")

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        return _parse_workbook(workbook)
    finally:
        workbook.close()
```

- [ ] **Step 5: Add lookup, change detection, and update helpers**

Add these helpers:

```python
SOURCE_FIELDS = (
    "title",
    "agency",
    "source_url",
    "opportunity_url",
    "due_date",
    "description_snippet",
    "extraction_confidence",
    "manual_review_needed",
    "source_status",
)


def _find_existing(db: Session, item: dict) -> Opportunity | None:
    external_id = item.get("external_id")
    if external_id:
        existing = (
            db.query(Opportunity)
            .filter(
                Opportunity.source_name == item.get("source_name"),
                Opportunity.external_id == external_id,
            )
            .first()
        )
        if existing:
            return existing
    return _find_duplicate(db, item)


def _source_changes(existing: Opportunity, item: dict) -> dict[str, dict[str, str | float | bool | None]]:
    changes: dict[str, dict[str, str | float | bool | None]] = {}
    for field in SOURCE_FIELDS:
        current = getattr(existing, field)
        incoming = item.get(field)
        if current != incoming:
            changes[field] = {"from": _serialize_change_value(current), "to": _serialize_change_value(incoming)}
    return changes


def _serialize_change_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _apply_source_updates(existing: Opportunity, item: dict) -> None:
    for field in SOURCE_FIELDS:
        setattr(existing, field, item.get(field))
    existing.last_seen_at = datetime.utcnow()
```

Rename `_is_duplicate` to `_find_duplicate` and return the row instead of a boolean:

```python
def _find_duplicate(db: Session, item: dict) -> Opportunity | None:
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
    )
```

- [ ] **Step 6: Update opportunity creation**

Update `_create_opportunity`:

```python
def _create_opportunity(db: Session, item: dict) -> Opportunity:
    now = datetime.utcnow()
    row = Opportunity(
        title=item["title"],
        agency=item["agency"],
        source_name=item["source_name"],
        source_url=item["source_url"],
        opportunity_url=item.get("opportunity_url"),
        external_id=item.get("external_id"),
        source_status=item.get("source_status"),
        due_date=item.get("due_date"),
        description_snippet=item.get("description_snippet"),
        extraction_confidence=item.get("extraction_confidence", 0.75),
        manual_review_needed=item.get("manual_review_needed", False),
        status="Saved",
        last_seen_at=now,
    )
    db.add(row)
    db.flush()
    return row
```

Do not commit inside `_create_opportunity`; the import run should commit once after all items are recorded.

- [ ] **Step 7: Implement upload import service**

Add this function:

```python
def import_emma_excel_upload(
    db: Session,
    contents: bytes,
    filename: str,
    content_type: str | None = None,
    profile: dict | None = None,
    auto_score: bool = True,
) -> dict:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("eMMA import requires a .xlsx file")

    profile = profile if profile is not None else load_business_profile()
    file_sha = hashlib.sha256(contents).hexdigest()
    run = ImportRun(
        source_name=EMMA_SOURCE_NAME,
        filename=filename,
        content_type=content_type,
        file_size_bytes=len(contents),
        file_sha256=file_sha,
        workbook_bytes=contents,
        status="completed",
    )
    db.add(run)
    db.flush()

    try:
        candidates = parse_emma_excel_bytes(contents)
    except ValueError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise

    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "scored": 0}
    for item in candidates:
        action, opportunity, change_summary, row_sha = _import_candidate(db, item, profile, auto_score, counts)
        db.add(
            ImportRunItem(
                import_run=run,
                opportunity=opportunity,
                external_id=item.get("external_id"),
                row_sha256=row_sha,
                action=action,
                change_summary=json.dumps(change_summary, sort_keys=True) if change_summary else None,
                raw_title=item.get("title"),
                raw_agency=item.get("agency"),
                raw_due_date=item.get("due_date").isoformat() if item.get("due_date") else None,
                raw_source_status=item.get("source_status"),
            )
        )

    run.rows_seen = len(candidates)
    run.created = counts["created"]
    run.updated = counts["updated"]
    run.unchanged = counts["unchanged"]
    run.skipped = counts["skipped"]
    run.scored = counts["scored"]
    db.commit()
    db.refresh(run)
    return _import_run_summary(run)
```

Add `_import_candidate` and summary helper:

```python
def _import_candidate(db: Session, item: dict, profile: dict, auto_score: bool, counts: dict):
    row_sha = _row_hash(item)
    existing = _find_existing(db, item)
    source_status = str(item.get("source_status") or "").strip().lower()

    if not existing and source_status != "open":
        counts["skipped"] += 1
        return "skipped", None, {"reason": "source status is not open"}, row_sha

    if not existing:
        row = _create_opportunity(db, item)
        counts["created"] += 1
        if auto_score:
            score_and_store_opportunity(db, row, profile)
            counts["scored"] += 1
        return "created", row, None, row_sha

    changes = _source_changes(existing, item)
    existing.last_seen_at = datetime.utcnow()
    if not changes:
        counts["unchanged"] += 1
        return "unchanged", existing, None, row_sha

    _apply_source_updates(existing, item)
    counts["updated"] += 1
    return "updated", existing, changes, row_sha


def _import_run_summary(run: ImportRun) -> dict:
    return {
        "ok": run.status == "completed",
        "import_run_id": run.id,
        "source": run.source_name,
        "filename": run.filename,
        "rows_seen": run.rows_seen,
        "created": run.created,
        "updated": run.updated,
        "unchanged": run.unchanged,
        "skipped": run.skipped,
        "scored": run.scored,
        "mock_fallback_used": False,
    }
```

- [ ] **Step 8: Preserve path import behavior**

Update `import_emma_excel` to use `_find_existing` and commits compatible with the new `_create_opportunity`:

```python
for item in candidates:
    if str(item.get("source_status") or "").strip().lower() != "open":
        continue
    if _find_existing(db, item):
        duplicates_skipped += 1
        continue
    row = _create_opportunity(db, item)
    created += 1
    if auto_score:
        score_and_store_opportunity(db, row, profile)
        scored += 1

db.commit()
```

Keep the existing response shape for the path endpoint.

- [ ] **Step 9: Run service tests**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_emma_excel_import_service.py -q
```

Expected: PASS.

---

## Task 3: Upload And Import History API Routes

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/schemas/imports.py`
- Modify: `local-contract-hunter-ai/backend/app/routes/imports.py`
- Create: `local-contract-hunter-ai/backend/tests/test_import_routes.py`

- [ ] **Step 1: Add route tests first**

Create `local-contract-hunter-ai/backend/tests/test_import_routes.py`:

```python
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
    sheet.append([
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
    ])
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
        files={"file": ("Public_Solicitations.xlsx", workbook_payload(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    run_id = upload.json()["import_run_id"]

    list_response = client.get("/api/import/runs")
    detail_response = client.get(f"/api/import/runs/{run_id}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run_id
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run_id
    assert detail_response.json()["items"][0]["action"] == "created"
```

- [ ] **Step 2: Run route tests and verify failure**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_import_routes.py -q
```

Expected: FAIL because upload/history routes are not implemented yet.

- [ ] **Step 3: Add import schemas**

Update `local-contract-hunter-ai/backend/app/schemas/imports.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EmmaExcelImportRequest(BaseModel):
    path: str
    auto_score: bool = True


class EmmaExcelImportResult(BaseModel):
    ok: bool
    import_run_id: int | None = None
    source: str
    filename: str | None = None
    rows_seen: int
    created: int
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    duplicates_skipped: int = 0
    scored: int
    mock_fallback_used: bool


class ImportRunItemRead(BaseModel):
    id: int
    opportunity_id: int | None
    external_id: str | None
    row_sha256: str | None
    action: str
    change_summary: str | None
    raw_title: str | None
    raw_agency: str | None
    raw_due_date: str | None
    raw_source_status: str | None

    class Config:
        from_attributes = True


class ImportRunRead(BaseModel):
    id: int
    source_name: str
    filename: str
    content_type: str | None
    file_size_bytes: int
    file_sha256: str
    uploaded_at: datetime
    rows_seen: int
    created: int
    updated: int
    unchanged: int
    skipped: int
    scored: int
    status: str
    error_message: str | None

    class Config:
        from_attributes = True


class ImportRunDetailRead(ImportRunRead):
    items: list[ImportRunItemRead] = []
```

- [ ] **Step 4: Add upload/history routes**

Update `local-contract-hunter-ai/backend/app/routes/imports.py` imports:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.models.import_run import ImportRun
from app.schemas.imports import (
    EmmaExcelImportRequest,
    EmmaExcelImportResult,
    ImportRunDetailRead,
    ImportRunRead,
)
from app.services.emma_excel_import_service import import_emma_excel, import_emma_excel_upload
```

Add route response models:

```python
@router.post("/emma-excel/upload", response_model=EmmaExcelImportResult)
async def upload_emma_excel_file(
    file: UploadFile = File(...),
    auto_score: bool = Form(True),
    db: Session = Depends(get_db),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="eMMA import requires a .xlsx file")
    contents = await file.read()
    try:
        return import_emma_excel_upload(
            db,
            contents,
            filename=filename,
            content_type=file.content_type,
            profile=load_business_profile(),
            auto_score=auto_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=list[ImportRunRead])
def list_import_runs(db: Session = Depends(get_db)):
    return db.query(ImportRun).order_by(ImportRun.uploaded_at.desc()).limit(10).all()


@router.get("/runs/{run_id}", response_model=ImportRunDetailRead)
def get_import_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(ImportRun)
        .options(joinedload(ImportRun.items))
        .filter(ImportRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")
    return run
```

- [ ] **Step 5: Run route and service tests**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_emma_excel_import_service.py tests/test_import_routes.py -q
```

Expected: PASS.

---

## Task 4: Frontend API Types And Upload Panel

**Files:**
- Modify: `local-contract-hunter-ai/frontend/lib/types.ts`
- Modify: `local-contract-hunter-ai/frontend/lib/api.ts`
- Modify: `local-contract-hunter-ai/frontend/components/EmmaExcelImportPanel.tsx`

- [ ] **Step 1: Update frontend types**

Update `Opportunity` in `local-contract-hunter-ai/frontend/lib/types.ts`:

```typescript
external_id?: string | null;
source_status?: string | null;
last_seen_at?: string | null;
updated_at?: string | null;
```

Replace `EmmaExcelImportResult` with:

```typescript
export type EmmaExcelImportResult = {
  ok: boolean;
  import_run_id?: number | null;
  source: string;
  filename?: string | null;
  rows_seen: number;
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  duplicates_skipped?: number;
  scored: number;
  mock_fallback_used: boolean;
};

export type ImportRun = {
  id: number;
  source_name: string;
  filename: string;
  content_type?: string | null;
  file_size_bytes: number;
  file_sha256: string;
  uploaded_at: string;
  rows_seen: number;
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  scored: number;
  status: string;
  error_message?: string | null;
};
```

- [ ] **Step 2: Update API client for multipart requests**

Update imports in `local-contract-hunter-ai/frontend/lib/api.ts`:

```typescript
  ImportRun,
```

Add a multipart helper:

```typescript
async function fetchForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store"
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    const detail = typeof errorBody?.detail === "string" ? errorBody.detail : null;
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json();
}
```

Add API methods:

```typescript
  uploadEmmaExcel: (file: File, autoScore = true) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("auto_score", String(autoScore));
    return fetchForm<EmmaExcelImportResult>("/api/import/emma-excel/upload", formData);
  },
  getImportRuns: () => fetchJson<ImportRun[]>("/api/import/runs"),
```

Keep `importEmmaExcel` temporarily so old local workflows still compile.

- [ ] **Step 3: Replace path input UI with file upload UI**

In `local-contract-hunter-ai/frontend/components/EmmaExcelImportPanel.tsx`, update imports:

```typescript
import { EmmaExcelImportResult, ImportRun } from "@/lib/types";
```

Replace state:

```typescript
const [file, setFile] = useState<File | null>(null);
const [autoScore, setAutoScore] = useState(true);
const [isImporting, setIsImporting] = useState(false);
const [result, setResult] = useState<EmmaExcelImportResult | null>(null);
const [history, setHistory] = useState<ImportRun[]>([]);
const [error, setError] = useState<string | null>(null);
```

Add history loading:

```typescript
async function refreshHistory() {
  const runs = await api.getImportRuns().catch(() => []);
  setHistory(runs);
}
```

Use `useEffect`:

```typescript
useEffect(() => {
  refreshHistory();
}, []);
```

Update import handler:

```typescript
async function handleImport() {
  if (!file) {
    setError("Choose the eMMA .xlsx workbook to upload.");
    return;
  }
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    setError("Choose a .xlsx workbook exported from eMMA.");
    return;
  }

  setIsImporting(true);
  setError(null);
  setResult(null);
  try {
    const importResult = await api.uploadEmmaExcel(file, autoScore);
    setResult(importResult);
    await refreshHistory();
    router.refresh();
  } catch (err) {
    setError(err instanceof Error ? err.message : "Import failed.");
  } finally {
    setIsImporting(false);
  }
}
```

Replace the label/input block with:

```tsx
<label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="emma-workbook-file">
  Workbook upload
</label>
<input
  id="emma-workbook-file"
  type="file"
  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
  className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm file:font-medium file:text-slate-700 focus:border-navy"
/>
{file && <div className="mt-1 text-xs text-slate-500">Selected: {file.name}</div>}
```

Update result display counts to include updated/unchanged/skipped:

```tsx
<div className="mt-1 text-xs text-emerald-800">
  {result.created} created, {result.updated} updated, {result.unchanged} unchanged from {result.source}.
</div>
```

Render six summary tiles:

```tsx
{[
  ["Rows read", result.rows_seen, "bg-slate-50 text-ink"],
  ["Created", result.created, "bg-emerald-50 text-emerald-900"],
  ["Updated", result.updated, "bg-blue-50 text-blue-900"],
  ["Unchanged", result.unchanged, "bg-slate-50 text-slate-900"],
  ["Skipped", result.skipped, "bg-amber-50 text-amber-900"],
  ["Scored", result.scored, "bg-indigo-50 text-indigo-900"],
].map(([label, value, classes]) => (
  <div key={label} className={`rounded-lg p-3 ${classes}`}>
    <div className="text-xs opacity-75">{label}</div>
    <div className="text-lg font-semibold">{value}</div>
  </div>
))}
```

Add recent history below result/errors:

```tsx
{history.length > 0 && (
  <div className="mt-4 border-t border-slate-200 pt-3">
    <div className="text-sm font-semibold text-ink">Recent imports</div>
    <div className="mt-2 space-y-2">
      {history.slice(0, 3).map((run) => (
        <div key={run.id} className="rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
          <div className="font-medium text-slate-900">{run.filename}</div>
          <div>{run.created} created, {run.updated} updated, {run.unchanged} unchanged, {run.skipped} skipped</div>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 4: Run frontend type check/build**

Run:

```bash
cd local-contract-hunter-ai/frontend
npm run build
```

Expected: PASS.

---

## Task 5: End-To-End Verification And Regression Tests

**Files:**
- Modify as needed only if test failures identify a defect in files from Tasks 1-4.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest tests/test_emma_excel_import_service.py tests/test_import_routes.py tests/test_search_service.py tests/test_search_routes.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all backend tests**

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest -q
```

Expected: PASS.

- [ ] **Step 3: Verify the local API upload route manually**

Start backend if needed:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. DATABASE_URL=sqlite:///./local_contract_hunter.db uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
curl -sS \
  -F "file=@../../docs/superpowers/emma_docs/Public_Solicitations.xlsx" \
  -F "auto_score=true" \
  http://localhost:8000/api/import/emma-excel/upload
```

Expected: JSON response includes `ok: true`, `import_run_id`, and count fields.

- [ ] **Step 4: Verify frontend upload UI**

Run:

```bash
cd local-contract-hunter-ai/frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`, upload `docs/superpowers/emma_docs/Public_Solicitations.xlsx`, and confirm:

- The request goes to `/api/import/emma-excel/upload`.
- The response is successful.
- The dashboard shows created/updated/unchanged/skipped/scored counts.
- Recent imports shows the uploaded filename.
- Re-uploading the same workbook increases unchanged count and does not duplicate opportunities.

- [ ] **Step 5: Check edited-file lints**

Use Cursor diagnostics or run:

```bash
cd local-contract-hunter-ai/frontend
npm run build
```

Expected: no TypeScript errors.

Run:

```bash
cd local-contract-hunter-ai/backend
PYTHONPATH=. pytest -q
```

Expected: no Python test failures.

---

## Self-Review

- Spec coverage:
  - Upload from dashboard: Task 4.
  - Import run records: Tasks 1-3.
  - Per-row import results: Tasks 1-3.
  - Stable BPM ID identity: Tasks 1-2.
  - Create new open opportunities: Task 2.
  - Update changed source fields: Task 2.
  - Preserve workflow status: Task 2 tests.
  - Source status changes: Task 2 tests.
  - New opportunity scoring: Task 2 tests.
  - Recent import history: Tasks 3-4.
- Placeholder scan: no placeholder markers are intentionally left in this plan.
- Type consistency: backend response fields match frontend `EmmaExcelImportResult`; route names match API client methods.
