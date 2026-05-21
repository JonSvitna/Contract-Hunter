# Maryland County Source Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add all Maryland county procurement sources and safely sync missing default sources into existing databases.

**Architecture:** Keep sources as YAML-backed defaults plus database rows. Extend `source_service` with an idempotent insert-missing sync that preserves existing DB edits, call it during startup, and expose a conservative manual sync endpoint. Add tests for sync behavior and source-pack coverage.

**Tech Stack:** FastAPI, SQLAlchemy, PyYAML, pytest, Next.js build verification.

---

## File Structure

- Modify `local-contract-hunter-ai/config/sources.yaml`: add all Maryland county procurement sources and Baltimore City procurement while preserving eMMA and existing school/library sources.
- Modify `local-contract-hunter-ai/backend/app/services/source_service.py`: add `sync_missing_seed_sources(db)`.
- Modify `local-contract-hunter-ai/backend/app/main.py`: call `sync_missing_seed_sources` on startup after first-run seeding.
- Modify `local-contract-hunter-ai/backend/app/routes/sources.py`: add `POST /api/sources/sync-defaults`.
- Create `local-contract-hunter-ai/backend/tests/test_source_service.py`: test sync idempotency, non-overwrite behavior, and county source coverage.
- Create or update `local-contract-hunter-ai/backend/tests/test_sources_routes.py`: test manual sync endpoint.

Do not commit unless the user explicitly requests a commit.

---

## Task 1: Source Sync Service

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/services/source_service.py`
- Test: `local-contract-hunter-ai/backend/tests/test_source_service.py`

- [ ] **Step 1: Write service tests**

Create `local-contract-hunter-ai/backend/tests/test_source_service.py` with:

```python
from __future__ import annotations

from app.models.source import Source
from app.services.source_service import load_seed_sources, sync_missing_seed_sources


MARYLAND_COUNTY_NAMES = {
    "Allegany County",
    "Anne Arundel County",
    "Baltimore County",
    "Calvert County",
    "Caroline County",
    "Carroll County",
    "Cecil County",
    "Charles County",
    "Dorchester County",
    "Frederick County",
    "Garrett County",
    "Harford County",
    "Howard County",
    "Kent County",
    "Montgomery County",
    "Prince George's County",
    "Queen Anne's County",
    "St. Mary's County",
    "Somerset County",
    "Talbot County",
    "Washington County",
    "Wicomico County",
    "Worcester County",
}


def test_sync_missing_seed_sources_inserts_missing_without_overwriting_existing(db_session):
    existing = Source(
        name="Howard County Procurement",
        url="https://custom.example.com/howard",
        source_type="generic",
        active=False,
        search_delay_seconds=9.0,
        notes="User edited",
    )
    db_session.add(existing)
    db_session.commit()

    created = sync_missing_seed_sources(db_session)
    db_session.refresh(existing)

    assert created > 0
    assert existing.url == "https://custom.example.com/howard"
    assert existing.active is False
    assert existing.search_delay_seconds == 9.0
    assert existing.notes == "User edited"
    assert db_session.query(Source).filter(Source.name == "Allegany County Bid Postings").count() == 1


def test_sync_missing_seed_sources_is_idempotent(db_session):
    first = sync_missing_seed_sources(db_session)
    second = sync_missing_seed_sources(db_session)

    assert first > 0
    assert second == 0
    assert db_session.query(Source).count() == len(load_seed_sources())


def test_seed_source_pack_includes_all_maryland_counties_and_baltimore_city():
    names = {source["name"] for source in load_seed_sources()}

    for county_name in MARYLAND_COUNTY_NAMES:
        assert any(county_name in source_name for source_name in names), county_name
    assert "Baltimore City Bid Opportunities" in names
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_source_service.py" -q
```

Expected: import fails because `sync_missing_seed_sources` does not exist yet.

- [ ] **Step 3: Implement source sync**

Add to `source_service.py`:

```python
def sync_missing_seed_sources(db: Session) -> int:
    created = 0
    existing_names = {name for (name,) in db.query(Source.name).all()}

    for source in load_seed_sources():
        if source["name"] in existing_names:
            continue
        row = Source(
            name=source["name"],
            url=source["url"],
            source_type=source.get("source_type", "generic"),
            active=source.get("active", True),
            search_delay_seconds=source.get("search_delay_seconds", settings.search_delay_seconds),
            notes=source.get("notes"),
        )
        db.add(row)
        existing_names.add(source["name"])
        created += 1

    if created:
        db.commit()
    return created
```

- [ ] **Step 4: Run service tests**

Run the same pytest command. Expected: source-pack coverage still fails until YAML is expanded.

---

## Task 2: Full County Source Pack

**Files:**
- Modify: `local-contract-hunter-ai/config/sources.yaml`
- Test: `local-contract-hunter-ai/backend/tests/test_source_service.py`

- [ ] **Step 1: Replace the county section of `sources.yaml`**

Keep `Maryland eMMA` and the school/library sources. Add or preserve these county/city entries:

```yaml
  - name: Allegany County Bid Postings
    url: https://www.alleganygov.org/bids.aspx
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Anne Arundel County Purchasing
    url: https://www.aacounty.org/departments/purchasing/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Baltimore City Bid Opportunities
    url: https://cityservices.baltimorecity.gov/suppliers/bid-opportunities
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County-equivalent city source

  - name: Baltimore County Procurement
    url: https://www.baltimorecountymd.gov/departments/purchasing
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Calvert County Procurement Office
    url: https://www.calvertcountymd.gov/255/Procurement-Office
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Caroline County Bid Opportunities
    url: https://www.carolinemd.org/Bids.aspx
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Carroll County Bids and Proposals
    url: https://www.carrollcountymd.gov/government/directory/commissioners/office-of-procurement/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Cecil County Procurement
    url: https://www.cecilcountymd.gov/269/Procurement
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Charles County Procurement Bid Opportunities
    url: https://www.charlescountymd.gov/business/procurement-bid-opportunities
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Dorchester County Procurement Watch
    url: https://dorchestercountymd.com/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source; official procurement page was not obvious, expect manual review fallback

  - name: Frederick County Procurement Contracts
    url: https://www.frederickcountymd.gov/176/Procurement-Contracts
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Garrett County Purchasing
    url: https://www.garrettcountymd.gov/financial-services/purchasing
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Harford County Procurement
    url: https://www.harfordcountymd.gov/390/Procurement
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Howard County Procurement
    url: https://www.howardcountymd.gov/procurement
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Kent County Request for Proposal
    url: https://www.kentcounty.com/government/request_for_proposal
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Montgomery County Procurement
    url: https://www.montgomerycountymd.gov/procurement/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Prince George's County Procurement
    url: https://www.princegeorgescountymd.gov/departments-offices/central-services/purchasing
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Queen Anne's County Bid Postings
    url: https://www.qac.org/bids.aspx
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: St. Mary's County Procurement
    url: https://www.stmaryscountymd.gov/procurement/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Somerset County Bids and Proposals
    url: https://www.somersetmd.us/government/bids_proposals.php
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Talbot County Procurement Policy
    url: https://www.talbotcountymd.gov/Topics-Of-Interest/talbot-county-procurement-policy
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source; official policy page, expect manual review fallback for live bids

  - name: Washington County Office of Procurement
    url: https://www.washco-md.net/office-of-procurement/
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Wicomico County Bid Postings
    url: https://www.wicomicocounty.org/Bids.aspx?CatID=All&Status=&showAllBids=on&txtSort=Category
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source

  - name: Worcester County Bid Board
    url: https://www.co.worcester.md.us/commissioners/bids
    source_type: generic
    active: true
    search_delay_seconds: 2.0
    notes: County source
```

- [ ] **Step 2: Run source service tests**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_source_service.py" -q
```

Expected: service tests pass.

---

## Task 3: Startup And Manual Sync Route

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/main.py`
- Modify: `local-contract-hunter-ai/backend/app/routes/sources.py`
- Test: `local-contract-hunter-ai/backend/tests/test_sources_routes.py`

- [ ] **Step 1: Add route test**

Create `local-contract-hunter-ai/backend/tests/test_sources_routes.py`:

```python
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
```

- [ ] **Step 2: Run route test to verify failure**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_sources_routes.py" -q
```

Expected: fails with 404 because the sync route does not exist.

- [ ] **Step 3: Add startup sync**

In `main.py`, update import:

```python
from app.services.source_service import seed_sources_if_empty, sync_missing_seed_sources
```

Inside startup:

```python
        seed_sources_if_empty(db)
        sync_missing_seed_sources(db)
```

- [ ] **Step 4: Add manual sync route**

In `routes/sources.py`, import:

```python
from app.services.source_service import sync_missing_seed_sources
```

Add route before `@router.patch("/{source_id}")`:

```python
@router.post("/sync-defaults")
def sync_default_sources(db: Session = Depends(get_db)):
    return {"created": sync_missing_seed_sources(db)}
```

- [ ] **Step 5: Run route tests**

Run the route test command again. Expected: pass.

---

## Task 4: Full Verification

**Files:**
- Modify only if verification reveals defects in touched files.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest \
  "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_source_service.py" \
  "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_sources_routes.py" \
  "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_search_routes.py" \
  -q
```

Expected: pass.

- [ ] **Step 2: Run full backend tests**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests" -q
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend" && npm run build
```

Expected: pass.

- [ ] **Step 4: Smoke-check YAML names**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" - <<'PY'
from app.services.source_service import load_seed_sources
sources = load_seed_sources()
print(len(sources))
print([s["name"] for s in sources if "County" in s["name"]][:5])
PY
```

Expected: source count includes all county/city plus eMMA and school/library sources.

---

## Self-Review

- Spec coverage:
  - Full Maryland county pack: Task 2.
  - Baltimore City procurement: Task 2.
  - Safe sync for existing databases: Tasks 1 and 3.
  - Preserve existing edits: Tasks 1 and 3 tests.
  - Manual sync endpoint: Task 3.
  - Validation path remains one-source-at-a-time: existing `/api/search/validate/source` remains unchanged and is included in verification.
- Placeholder scan: no placeholders or incomplete steps are intentionally left in this plan.
- Type consistency:
  - `sync_missing_seed_sources(db: Session) -> int` is used consistently by startup, route, and tests.
  - Route response shape is consistently `{"created": int}`.
