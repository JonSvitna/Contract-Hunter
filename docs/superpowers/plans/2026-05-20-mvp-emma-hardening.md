# MVP eMMA Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the local MVP with one real Maryland eMMA opportunity that is extracted, persisted, scored, and visible in the dashboard/detail flow.

**Architecture:** Keep the existing FastAPI, Next.js, YAML, SQLAlchemy, and SQLite scaffold. Add a narrow eMMA validation API path that runs eMMA only, disables mock fallback for acceptance, scores newly created rows during the run, and returns enough diagnostics to prove whether live extraction succeeded.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PyYAML, Playwright, pytest, Next.js 14, React 18, Tailwind CSS, TypeScript.

---

## File Structure

- Modify: `local-contract-hunter-ai/backend/requirements.txt`
  - Add `pytest` so backend behavior can be validated repeatably.
- Create: `local-contract-hunter-ai/backend/tests/conftest.py`
  - Provide test import paths, temp SQLite database setup, and SQLAlchemy sessions.
- Create: `local-contract-hunter-ai/backend/tests/test_score_persistence.py`
  - Verify score upsert behavior independently from routes.
- Create: `local-contract-hunter-ai/backend/tests/test_search_service.py`
  - Verify source filtering, no-mock validation behavior, duplicate prevention, and auto-scoring.
- Create: `local-contract-hunter-ai/backend/tests/test_emma_scraper.py`
  - Verify eMMA candidate normalization from representative links and manual-review fallback.
- Create: `local-contract-hunter-ai/backend/app/services/score_persistence.py`
  - Upsert score rows for opportunities and reuse route scoring logic.
- Create: `local-contract-hunter-ai/backend/app/services/search_service.py`
  - Move search orchestration out of the route, add source filtering, mock fallback control, auto-scoring, and diagnostics.
- Modify: `local-contract-hunter-ai/backend/app/routes/search.py`
  - Keep existing routes and add `POST /api/search/validate/emma`.
- Modify: `local-contract-hunter-ai/backend/app/routes/scoring.py`
  - Use shared score upsert service.
- Modify: `local-contract-hunter-ai/backend/app/scrapers/emma_scraper.py`
  - Replace the generic subclass with eMMA-specific normalization and diagnostics.
- Modify: `local-contract-hunter-ai/frontend/components/OpportunityCard.tsx`
  - Show manual-review state and source link metadata on cards.
- Modify: `local-contract-hunter-ai/frontend/app/opportunities/[id]/page.tsx`
  - Show extraction confidence and manual-review state on detail pages.
- Create: `local-contract-hunter-ai/docs/EMMA_VALIDATION_RUNBOOK.md`
  - Document the local validation sequence and acceptance checks.

## Task 1: Backend Test Harness

**Files:**
- Modify: `local-contract-hunter-ai/backend/requirements.txt`
- Create: `local-contract-hunter-ai/backend/tests/conftest.py`

- [ ] **Step 1: Add pytest to backend requirements**

Append this line to `local-contract-hunter-ai/backend/requirements.txt`:

```text
pytest
```

- [ ] **Step 2: Create test fixtures**

Create `local-contract-hunter-ai/backend/tests/conftest.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base  # noqa: E402
from app.models.opportunity import Opportunity  # noqa: F401,E402
from app.models.score import OpportunityScore  # noqa: F401,E402
from app.models.source import Source  # noqa: F401,E402


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
```

- [ ] **Step 3: Install dependencies**

Run:

```bash
cd local-contract-hunter-ai/backend
pip install -r requirements.txt
```

Expected: installation completes and includes `pytest`.

- [ ] **Step 4: Verify empty test suite runs**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest -q
```

Expected: pytest starts successfully. It may report `no tests ran` until Task 2 adds tests.

- [ ] **Step 5: Commit**

```bash
git add local-contract-hunter-ai/backend/requirements.txt local-contract-hunter-ai/backend/tests/conftest.py
git commit -m "test: add backend pytest harness"
```

## Task 2: Shared Score Persistence

**Files:**
- Create: `local-contract-hunter-ai/backend/tests/test_score_persistence.py`
- Create: `local-contract-hunter-ai/backend/app/services/score_persistence.py`
- Modify: `local-contract-hunter-ai/backend/app/routes/scoring.py`

- [ ] **Step 1: Write failing tests for score upsert**

Create `local-contract-hunter-ai/backend/tests/test_score_persistence.py`:

```python
from __future__ import annotations

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.services.score_persistence import score_and_store_opportunity


def test_score_and_store_creates_score(db_session):
    opportunity = Opportunity(
        title="Cybersecurity Vulnerability Assessment",
        agency="Maryland eMMA",
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/123",
        description_snippet="NIST risk assessment and vulnerability scanning support.",
        extraction_confidence=0.85,
        manual_review_needed=False,
        status="Saved",
    )
    db_session.add(opportunity)
    db_session.commit()
    db_session.refresh(opportunity)

    payload = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})

    stored = db_session.query(OpportunityScore).filter_by(opportunity_id=opportunity.id).one()
    assert payload["recommendation"] in {"Pursue", "Watch", "Skip", "Manual Review"}
    assert stored.opportunity_id == opportunity.id
    assert stored.fit_score == payload["fit_score"]
    assert stored.next_steps.startswith("[")


def test_score_and_store_updates_existing_score(db_session):
    opportunity = Opportunity(
        title="Cybersecurity Policy Review",
        agency="Maryland eMMA",
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/456",
        description_snippet="Compliance documentation and NIST policy review.",
        extraction_confidence=0.8,
        manual_review_needed=False,
        status="Saved",
    )
    db_session.add(opportunity)
    db_session.commit()
    db_session.refresh(opportunity)

    first = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})
    opportunity.description_snippet = "24/7 SOC monitoring and managed services."
    second = score_and_store_opportunity(db_session, opportunity, {"name": "Sean"})

    stored_rows = db_session.query(OpportunityScore).filter_by(opportunity_id=opportunity.id).all()
    assert len(stored_rows) == 1
    assert second["fit_score"] <= first["fit_score"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_score_persistence.py -q
```

Expected: failure with `ModuleNotFoundError: No module named 'app.services.score_persistence'`.

- [ ] **Step 3: Implement score persistence service**

Create `local-contract-hunter-ai/backend/app/services/score_persistence.py`:

```python
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.services.scoring_service import score_opportunity


def score_and_store_opportunity(
    db: Session,
    opportunity: Opportunity,
    profile: dict,
) -> dict:
    payload = score_opportunity(opportunity, profile)
    existing = (
        db.query(OpportunityScore)
        .filter(OpportunityScore.opportunity_id == opportunity.id)
        .first()
    )
    serialized_payload = {
        key: json.dumps(value) if key == "next_steps" else value
        for key, value in payload.items()
    }

    if existing:
        for key, value in serialized_payload.items():
            setattr(existing, key, value)
        row = existing
    else:
        row = OpportunityScore(
            opportunity_id=opportunity.id,
            **serialized_payload,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return payload
```

- [ ] **Step 4: Update scoring route to use service**

Replace the body of `score_single_opportunity` in `local-contract-hunter-ai/backend/app/routes/scoring.py` with:

```python
@router.post("/{opportunity_id}/score")
def score_single_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    profile = load_business_profile()
    payload = score_and_store_opportunity(db, opportunity, profile)
    return {"ok": True, "score": payload}
```

Also remove the unused `json` and `OpportunityScore` imports, then add:

```python
from app.services.score_persistence import score_and_store_opportunity
```

- [ ] **Step 5: Run score tests**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_score_persistence.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add local-contract-hunter-ai/backend/app/routes/scoring.py local-contract-hunter-ai/backend/app/services/score_persistence.py local-contract-hunter-ai/backend/tests/test_score_persistence.py
git commit -m "feat: share score persistence logic"
```

## Task 3: Search Service And eMMA Validation API

**Files:**
- Create: `local-contract-hunter-ai/backend/tests/test_search_service.py`
- Create: `local-contract-hunter-ai/backend/app/services/search_service.py`
- Modify: `local-contract-hunter-ai/backend/app/routes/search.py`

- [ ] **Step 1: Write failing search service tests**

Create `local-contract-hunter-ai/backend/tests/test_search_service.py`:

```python
from __future__ import annotations

from datetime import date

from app.models.opportunity import Opportunity
from app.models.source import Source
from app.services import search_service
from app.services.search_service import SearchRunOptions, execute_search


class FakeScraper:
    def __init__(self, candidates):
        self.candidates = candidates

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        return self.candidates


def test_execute_search_filters_to_emma_and_scores_new_rows(db_session, monkeypatch):
    emma = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    county = Source(
        name="County Source",
        url="https://example.com/county",
        source_type="generic",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add_all([emma, county])
    db_session.commit()

    candidates = [
        {
            "title": "Cybersecurity Risk Assessment",
            "agency": "Maryland Department of Test",
            "source_name": "Maryland eMMA",
            "source_url": "https://emma.maryland.gov/",
            "opportunity_url": "https://emma.maryland.gov/opportunity/1",
            "due_date": date(2099, 1, 15),
            "description_snippet": "NIST cybersecurity risk assessment and policy review.",
            "extraction_confidence": 0.9,
            "manual_review_needed": False,
        }
    ]

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity", "NIST"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper(candidates))

    result = execute_search(
        db_session,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )

    rows = db_session.query(Opportunity).all()
    assert result["ok"] is True
    assert result["sources"] == 1
    assert result["created"] == 1
    assert result["scored"] == 1
    assert result["mock_fallback_used"] is False
    assert rows[0].source_name == "Maryland eMMA"
    assert rows[0].score is not None


def test_execute_search_skips_duplicates_on_second_run(db_session, monkeypatch):
    source = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    candidates = [
        {
            "title": "Cybersecurity Risk Assessment",
            "agency": "Maryland Department of Test",
            "source_name": "Maryland eMMA",
            "source_url": "https://emma.maryland.gov/",
            "opportunity_url": "https://emma.maryland.gov/opportunity/1",
            "due_date": date(2099, 1, 15),
            "description_snippet": "NIST cybersecurity risk assessment and policy review.",
            "extraction_confidence": 0.9,
            "manual_review_needed": False,
        }
    ]

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity", "NIST"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper(candidates))

    first = execute_search(db_session, SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True))
    second = execute_search(db_session, SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True))

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["duplicates_skipped"] == 1
    assert db_session.query(Opportunity).count() == 1


def test_execute_search_validation_does_not_insert_mock_fallback(db_session, monkeypatch):
    source = Source(
        name="Maryland eMMA",
        url="https://emma.maryland.gov/",
        source_type="emma",
        active=True,
        search_delay_seconds=0.5,
    )
    db_session.add(source)
    db_session.commit()

    monkeypatch.setattr(search_service, "load_business_profile", lambda: {"name": "Sean"})
    monkeypatch.setattr(search_service, "load_keywords", lambda: ["cybersecurity"])
    monkeypatch.setattr(search_service, "get_scraper_for_source", lambda source: FakeScraper([]))

    result = execute_search(
        db_session,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )

    assert result["created"] == 0
    assert result["mock_fallback_used"] is False
    assert db_session.query(Opportunity).count() == 0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_search_service.py -q
```

Expected: failure with `ModuleNotFoundError: No module named 'app.services.search_service'`.

- [ ] **Step 3: Implement search service**

Create `local-contract-hunter-ai/backend/app/services/search_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.models.source import Source
from app.scrapers.emma_scraper import EmmaScraper
from app.scrapers.generic_procurement_scraper import GenericProcurementScraper
from app.services.score_persistence import score_and_store_opportunity
from app.services.source_service import (
    get_effective_throttle_for_source,
    load_business_profile,
    load_keywords,
)


@dataclass(frozen=True)
class SearchRunOptions:
    source_type: str | None = None
    source_name: str | None = None
    allow_mock_fallback: bool = True
    auto_score: bool = False


def mock_candidates(source_name: str, source_url: str) -> list[dict]:
    return [
        {
            "title": "Cybersecurity Vulnerability Assessment Services",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": "Local cybersecurity assessment and policy review support for municipal IT.",
            "extraction_confidence": 0.5,
            "manual_review_needed": True,
        },
        {
            "title": "NIST Gap Analysis and Security Awareness Training",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": "Short-term advisory engagement suitable for a solo consultant.",
            "extraction_confidence": 0.45,
            "manual_review_needed": True,
        },
    ]


def get_scraper_for_source(source: Source):
    throttle = get_effective_throttle_for_source(source.name)
    kwargs = {
        "delay_seconds": source.search_delay_seconds,
        "max_candidate_links": int(throttle.get("max_candidate_links", 120)),
        "page_timeout_ms": int(throttle.get("page_timeout_ms", 20000)),
        "body_timeout_ms": int(throttle.get("body_timeout_ms", 5000)),
    }
    if source.source_type.lower() == "emma":
        return EmmaScraper(**kwargs)
    return GenericProcurementScraper(**kwargs)


def _query_sources(db: Session, options: SearchRunOptions) -> list[Source]:
    query = db.query(Source).filter(Source.active.is_(True))
    if options.source_type:
        query = query.filter(Source.source_type.ilike(options.source_type))
    if options.source_name:
        query = query.filter(Source.name == options.source_name)
    return query.all()


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


def _create_opportunity(db: Session, source: Source, item: dict) -> Opportunity:
    row = Opportunity(
        title=item.get("title") or f"Opportunity from {source.name}",
        agency=item.get("agency") or source.name,
        source_name=source.name,
        source_url=source.url,
        opportunity_url=item.get("opportunity_url"),
        due_date=item.get("due_date"),
        description_snippet=item.get("description_snippet"),
        extraction_confidence=item.get("extraction_confidence", 0.4),
        manual_review_needed=item.get("manual_review_needed", False),
        status="Saved",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def execute_search(db: Session, options: SearchRunOptions | None = None) -> dict:
    options = options or SearchRunOptions()
    profile = load_business_profile()
    keywords = load_keywords()
    sources = _query_sources(db, options)
    created = 0
    skipped = 0
    scored = 0
    mock_fallback_used = False
    diagnostics: list[dict] = []

    for source in sources:
        scraper = get_scraper_for_source(source)
        candidates = scraper.scrape(source.name, source.url, keywords)
        diagnostics.append(
            {
                "source": source.name,
                "source_type": source.source_type,
                "candidates": len(candidates),
            }
        )

        for item in candidates:
            if _is_duplicate(db, item):
                skipped += 1
                continue
            row = _create_opportunity(db, source, item)
            created += 1
            if options.auto_score:
                score_and_store_opportunity(db, row, profile)
                scored += 1

    if created == 0 and sources and options.allow_mock_fallback:
        fallback_source = sources[0]
        mock_fallback_used = True
        for item in mock_candidates(fallback_source.name, fallback_source.url):
            if _is_duplicate(db, item):
                continue
            row = _create_opportunity(db, fallback_source, item)
            created += 1
            if options.auto_score:
                score_and_store_opportunity(db, row, profile)
                scored += 1

    return {
        "ok": True,
        "created": created,
        "duplicates_skipped": skipped,
        "sources": len(sources),
        "profile_name": profile.get("name", "Unknown"),
        "scored": scored,
        "mock_fallback_used": mock_fallback_used,
        "diagnostics": diagnostics,
    }
```

- [ ] **Step 4: Update search route to use service**

In `local-contract-hunter-ai/backend/app/routes/search.py`, remove `_mock_candidates`, `_execute_search`, scraper imports, duplicate-query imports, `Opportunity`, and `Source` imports. Add:

```python
from app.services.search_service import SearchRunOptions, execute_search
```

Update the existing route functions:

```python
@router.post("/run")
def run_search(db: Session = Depends(get_db)):
    return execute_search(db, SearchRunOptions())


@router.post("/validate/emma")
def validate_emma_search(db: Session = Depends(get_db)):
    return execute_search(
        db,
        SearchRunOptions(source_type="emma", allow_mock_fallback=False, auto_score=True),
    )
```

In `run_search_now`, replace:

```python
result = _execute_search(db)
```

with:

```python
result = execute_search(db, SearchRunOptions())
```

- [ ] **Step 5: Run search service tests**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_search_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Run score tests too**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_score_persistence.py tests/test_search_service.py -q
```

Expected: `5 passed`.

- [ ] **Step 7: Commit**

```bash
git add local-contract-hunter-ai/backend/app/routes/search.py local-contract-hunter-ai/backend/app/services/search_service.py local-contract-hunter-ai/backend/tests/test_search_service.py
git commit -m "feat: add eMMA validation search path"
```

## Task 4: eMMA Scraper Normalization

**Files:**
- Create: `local-contract-hunter-ai/backend/tests/test_emma_scraper.py`
- Modify: `local-contract-hunter-ai/backend/app/scrapers/emma_scraper.py`

- [ ] **Step 1: Write failing eMMA scraper tests**

Create `local-contract-hunter-ai/backend/tests/test_emma_scraper.py`:

```python
from __future__ import annotations

from app.scrapers.emma_scraper import EmmaScraper, normalize_emma_anchor


def test_normalize_emma_anchor_accepts_solicitation_link():
    item = normalize_emma_anchor(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text="BPM046789 Cybersecurity Risk Assessment Maryland Department of Test Due Date: 12/31/2099",
        href="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/46789",
        keywords=["cybersecurity", "risk assessment"],
    )

    assert item is not None
    assert item["title"].startswith("BPM046789 Cybersecurity Risk Assessment")
    assert item["agency"] == "Maryland Department of Test"
    assert item["opportunity_url"].endswith("/46789")
    assert item["due_date"].isoformat() == "2099-12-31"
    assert item["extraction_confidence"] >= 0.75
    assert item["manual_review_needed"] is False


def test_normalize_emma_anchor_rejects_navigation_link():
    item = normalize_emma_anchor(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        text="Login",
        href="https://emma.maryland.gov/page.aspx/en/usr/login",
        keywords=["cybersecurity"],
    )

    assert item is None


def test_manual_review_result_names_emma_failure():
    scraper = EmmaScraper()
    item = scraper.manual_review_result(
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        reason="No public solicitation links matched configured keywords.",
    )

    assert item["title"] == "Manual review needed for Maryland eMMA"
    assert item["manual_review_needed"] is True
    assert item["extraction_confidence"] == 0.2
    assert "No public solicitation links" in item["description_snippet"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_emma_scraper.py -q
```

Expected: failure because `normalize_emma_anchor` and `manual_review_result` do not exist yet.

- [ ] **Step 3: Implement eMMA normalization and scraper**

Replace `local-contract-hunter-ai/backend/app/scrapers/emma_scraper.py` with:

```python
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from app.scrapers.base_scraper import BaseScraper
from app.services.extraction_service import (
    confidence_from_text,
    parse_possible_due_date,
    snippet_with_keywords,
)

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


EMMA_SOLICITATION_PATTERNS = [
    "bpm",
    "bid",
    "sourcing",
    "solicitation",
    "process_manage_extranet",
    "request_browse_public",
]


def _looks_like_emma_opportunity(text: str, href: str, keywords: list[str]) -> bool:
    lowered_text = text.lower()
    lowered_href = href.lower()
    if any(nav in lowered_text for nav in ["login", "register", "help", "training", "contact"]):
        return False
    has_emma_pattern = any(pattern in lowered_href or pattern in lowered_text for pattern in EMMA_SOLICITATION_PATTERNS)
    has_keyword = any(keyword.lower() in lowered_text for keyword in keywords)
    return has_emma_pattern and has_keyword


def _agency_from_text(text: str, source_name: str) -> str:
    match = re.search(r"(Maryland [A-Za-z0-9&.,' -]+?)(?: Due Date:| Closing Date:|$)", text)
    if match:
        return match.group(1).strip()
    return source_name


def normalize_emma_anchor(
    source_name: str,
    source_url: str,
    text: str,
    href: str,
    keywords: list[str],
) -> dict | None:
    cleaned_text = " ".join(text.split())
    if not cleaned_text or not href:
        return None
    if not _looks_like_emma_opportunity(cleaned_text, href, keywords):
        return None

    opportunity_url = urljoin(source_url, href)
    return {
        "title": cleaned_text[:500],
        "agency": _agency_from_text(cleaned_text, source_name),
        "source_name": source_name,
        "source_url": source_url,
        "opportunity_url": opportunity_url,
        "due_date": parse_possible_due_date(cleaned_text),
        "description_snippet": snippet_with_keywords(cleaned_text, keywords),
        "extraction_confidence": confidence_from_text(cleaned_text, keywords),
        "manual_review_needed": False,
    }


class EmmaScraper(BaseScraper):
    def __init__(
        self,
        delay_seconds: float = 2.0,
        max_candidate_links: int = 120,
        page_timeout_ms: int = 20000,
        body_timeout_ms: int = 5000,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.max_candidate_links = max_candidate_links
        self.page_timeout_ms = page_timeout_ms
        self.body_timeout_ms = body_timeout_ms

    def manual_review_result(self, source_name: str, source_url: str, reason: str) -> dict:
        return {
            "title": f"Manual review needed for {source_name}",
            "agency": source_name,
            "source_name": source_name,
            "source_url": source_url,
            "opportunity_url": source_url,
            "due_date": None,
            "description_snippet": reason,
            "extraction_confidence": 0.2,
            "manual_review_needed": True,
        }

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        if sync_playwright is None:
            return [
                self.manual_review_result(
                    source_name,
                    source_url,
                    "Playwright is not installed locally. eMMA source retained for manual review.",
                )
            ]

        results: list[dict] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(source_url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
                time.sleep(self.delay_seconds)
                page_text = page.locator("body").inner_text(timeout=self.body_timeout_ms)
                anchors = page.eval_on_selector_all(
                    "a",
                    "(elements, limit) => elements.slice(0, limit).map(e => ({href: e.href || '', text: (e.innerText || e.textContent || '').trim()}))",
                    self.max_candidate_links,
                )

                for anchor in anchors:
                    item = normalize_emma_anchor(
                        source_name=source_name,
                        source_url=source_url,
                        text=anchor.get("text") or "",
                        href=anchor.get("href") or "",
                        keywords=keywords,
                    )
                    if item:
                        results.append(item)

                if results:
                    return results

                if any(keyword.lower() in page_text.lower() for keyword in keywords):
                    return [
                        self.manual_review_result(
                            source_name,
                            source_url,
                            "eMMA page contained configured keywords, but no public solicitation links matched the extractor.",
                        )
                    ]

                return [
                    self.manual_review_result(
                        source_name,
                        source_url,
                        "No public solicitation links matched configured keywords.",
                    )
                ]
            except Exception as exc:
                return [
                    self.manual_review_result(
                        source_name,
                        source_url,
                        f"eMMA scrape failed gracefully: {str(exc)[:200]}",
                    )
                ]
            finally:
                context.close()
                browser.close()
```

- [ ] **Step 4: Run eMMA scraper tests**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest tests/test_emma_scraper.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Run all backend tests**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add local-contract-hunter-ai/backend/app/scrapers/emma_scraper.py local-contract-hunter-ai/backend/tests/test_emma_scraper.py
git commit -m "feat: harden eMMA scraper normalization"
```

## Task 5: Frontend Validation Display

**Files:**
- Modify: `local-contract-hunter-ai/frontend/components/OpportunityCard.tsx`
- Modify: `local-contract-hunter-ai/frontend/app/opportunities/[id]/page.tsx`

- [ ] **Step 1: Update opportunity cards**

In `local-contract-hunter-ai/frontend/components/OpportunityCard.tsx`, add this block after the confidence line inside the metadata row:

```tsx
{item.manual_review_needed && (
  <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
    Manual review
  </span>
)}
```

Then replace the existing detail link wrapper:

```tsx
<div className="mt-4">
  <Link
    href={`/opportunities/${item.id}`}
    className="inline-flex rounded-md bg-navy px-3 py-2 text-sm font-medium text-white"
  >
    View details
  </Link>
</div>
```

with:

```tsx
<div className="mt-4 flex flex-wrap gap-2">
  <Link
    href={`/opportunities/${item.id}`}
    className="inline-flex rounded-md bg-navy px-3 py-2 text-sm font-medium text-white"
  >
    View details
  </Link>
  {(item.opportunity_url || item.source_url) && (
    <a
      href={item.opportunity_url || item.source_url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700"
    >
      Open source
    </a>
  )}
</div>
```

- [ ] **Step 2: Update opportunity detail extraction metadata**

In `local-contract-hunter-ai/frontend/app/opportunities/[id]/page.tsx`, add these rows inside the detail metadata grid after current status:

```tsx
<div>Extraction confidence: {Math.round(item.extraction_confidence * 100)}%</div>
<div>Manual review needed: {item.manual_review_needed ? "Yes" : "No"}</div>
```

- [ ] **Step 3: Build frontend**

Run:

```bash
cd local-contract-hunter-ai/frontend
npm install
npm run build
```

Expected: Next.js build completes without TypeScript or rendering errors.

- [ ] **Step 4: Commit**

```bash
git add local-contract-hunter-ai/frontend/components/OpportunityCard.tsx local-contract-hunter-ai/frontend/app/opportunities/[id]/page.tsx
git commit -m "feat: show extraction validation details"
```

## Task 6: Local eMMA Validation Runbook

**Files:**
- Create: `local-contract-hunter-ai/docs/EMMA_VALIDATION_RUNBOOK.md`

- [ ] **Step 1: Write runbook**

Create `local-contract-hunter-ai/docs/EMMA_VALIDATION_RUNBOOK.md`:

```markdown
# eMMA Validation Runbook

## Goal

Prove one real Maryland eMMA opportunity can move through the local MVP pipeline: scrape, persist, score, dashboard card, detail page, and duplicate prevention.

## Start Backend

```bash
cd local-contract-hunter-ai/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"Local Contract Hunter AI"}
```

## Start Frontend

```bash
cd local-contract-hunter-ai/frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Run eMMA Validation

```bash
curl -X POST http://localhost:8000/api/search/validate/emma
```

Successful acceptance response has:

```json
{
  "ok": true,
  "created": 1,
  "sources": 1,
  "scored": 1,
  "mock_fallback_used": false
}
```

`created` can be greater than 1. `created: 0` is acceptable only when the response shows `duplicates_skipped` after a previous successful run.

## Inspect API Data

```bash
curl http://localhost:8000/api/opportunities
```

Confirm at least one opportunity has:

- `source_name` from Maryland eMMA.
- A non-empty `title`.
- A non-empty `agency`.
- A source link.
- `extraction_confidence`.
- `score.recommendation`.
- `score.reasoning`.

## Confirm Dashboard

1. Open `http://localhost:3000`.
2. Confirm the eMMA opportunity appears in Top opportunities.
3. Open the opportunity detail page.
4. Confirm source link, extraction confidence, manual-review state, score breakdown, reasoning, next steps, and status buttons are visible.

## Confirm Duplicate Prevention

Run validation again:

```bash
curl -X POST http://localhost:8000/api/search/validate/emma
```

Expected response after a previous successful run:

```json
{
  "ok": true,
  "created": 0,
  "duplicates_skipped": 1,
  "sources": 1,
  "mock_fallback_used": false
}
```

`duplicates_skipped` can be greater than 1 if the first run found multiple real opportunities.

## Failure State

If eMMA blocks automation, changes selectors, or has no matching live opportunities, the validation endpoint must return `mock_fallback_used: false` and diagnostics that explain the failure. Mock fallback rows do not satisfy acceptance.
```

- [ ] **Step 2: Run backend tests**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd local-contract-hunter-ai/frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add local-contract-hunter-ai/docs/EMMA_VALIDATION_RUNBOOK.md
git commit -m "docs: add eMMA validation runbook"
```

## Task 7: End-To-End Local Acceptance

**Files:**
- No planned source edits unless validation exposes a concrete defect.

- [ ] **Step 1: Run full backend test suite**

Run:

```bash
cd local-contract-hunter-ai/backend
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd local-contract-hunter-ai/frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Start backend**

Run:

```bash
cd local-contract-hunter-ai/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Expected: server starts on `http://127.0.0.1:8000`.

- [ ] **Step 4: Start frontend**

Run:

```bash
cd local-contract-hunter-ai/frontend
npm run dev
```

Expected: app starts on `http://localhost:3000`.

- [ ] **Step 5: Run eMMA validation endpoint**

Run:

```bash
curl -X POST http://localhost:8000/api/search/validate/emma
```

Expected for first successful acceptance:

```json
{
  "ok": true,
  "created": 1,
  "sources": 1,
  "scored": 1,
  "mock_fallback_used": false
}
```

- [ ] **Step 6: Verify API output**

Run:

```bash
curl http://localhost:8000/api/opportunities
```

Expected: at least one Maryland eMMA opportunity includes a score object with `fit_score`, `recommendation`, `reasoning`, and `next_steps`.

- [ ] **Step 7: Verify duplicate behavior**

Run:

```bash
curl -X POST http://localhost:8000/api/search/validate/emma
```

Expected: `created` is `0` for already-seen postings and `duplicates_skipped` is at least `1`.

- [ ] **Step 8: Verify dashboard manually**

Open `http://localhost:3000` and confirm:

- The real eMMA opportunity appears in the dashboard.
- The opportunity card shows score/recommendation, confidence, and manual-review state when applicable.
- The detail page shows links, score breakdown, reasoning, next steps, and status controls.

- [ ] **Step 9: Confirm working tree state**

Run:

```bash
git status --short
```

Expected: no uncommitted changes from this plan remain. The pre-existing `.DS_Store` change may still appear and should not be included in plan commits.

## Self-Review Notes

- Spec coverage: source isolation, eMMA extraction, persistence, duplicate prevention, scoring, frontend display, error handling, tests, and runbook are covered by Tasks 1-7.
- Placeholder scan: no task depends on unspecified file paths or unnamed future work.
- Type consistency: plan uses existing `Opportunity`, `OpportunityScore`, `Source`, `SearchRunOptions`, `score_and_store_opportunity`, and `execute_search` names consistently.
