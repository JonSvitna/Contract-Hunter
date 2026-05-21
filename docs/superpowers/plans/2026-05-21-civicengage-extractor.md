# CivicEngage Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CivicEngage-specific bid scraper so `Bids.aspx` county sources produce specific bid candidates instead of broad manual-review fallback rows.

**Architecture:** Keep the existing `get_scraper_for_source()` entry point. Add a `CivicEngageBidScraper` with the same `BaseScraper` contract as the generic scraper, then update scraper selection to use it when a source URL path contains `bids.aspx`. Source run history stays unchanged and records the improved candidates automatically through existing `execute_search()` logic.

**Tech Stack:** FastAPI service layer, Playwright sync API, pytest fake scraper/page tests, SQLAlchemy-backed source run history.

---

## File Structure

- Create `local-contract-hunter-ai/backend/app/scrapers/civicengage_bid_scraper.py`: CivicEngage bid listing scraper.
- Modify `local-contract-hunter-ai/backend/app/services/search_service.py`: select the CivicEngage scraper for `Bids.aspx` URLs.
- Create `local-contract-hunter-ai/backend/tests/test_civicengage_bid_scraper.py`: unit tests with fake Playwright pages.
- Modify `local-contract-hunter-ai/backend/tests/test_search_service.py`: verify scraper selection and source run item recording for CivicEngage sources.

Do not commit unless the user explicitly requests a commit.

---

## Task 1: CivicEngage Scraper Tests

**Files:**
- Create: `local-contract-hunter-ai/backend/tests/test_civicengage_bid_scraper.py`

- [ ] **Step 1: Add fake Playwright test helpers**

Create `test_civicengage_bid_scraper.py` with fake page/context/browser classes modeled after `test_generic_procurement_scraper.py`. Include anchors, body text, close-error injection, and `install_fake_playwright()`.

- [ ] **Step 2: Add scraper behavior tests**

Add tests that assert:

- A `Bids.aspx?bidID=123` anchor with cybersecurity text creates one non-manual-review candidate.
- A `Bids.aspx?bidID=456` anchor without keyword text still creates one manual-review candidate with the specific bid URL.
- Duplicate `bidID` links are emitted once.
- A page with no bid links returns one manual-review fallback row.
- Context/browser close failures do not escape.

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_civicengage_bid_scraper.py -q
```

Expected: import failure because `app.scrapers.civicengage_bid_scraper` does not exist yet.

---

## Task 2: CivicEngage Scraper Implementation

**Files:**
- Create: `local-contract-hunter-ai/backend/app/scrapers/civicengage_bid_scraper.py`
- Test: `local-contract-hunter-ai/backend/tests/test_civicengage_bid_scraper.py`

- [ ] **Step 1: Implement scraper**

Create `CivicEngageBidScraper` with:

- Constructor matching `GenericProcurementScraper`.
- `scrape(source_name, source_url, keywords)` method.
- Playwright loading and anchor extraction.
- Candidate filtering for bid detail links and bid/RFP/proposal/solicitation/quote text.
- Deduplication by URL.
- Manual-review fallback when no candidates are found.
- Cleanup wrapped with `contextlib.suppress(Exception)`.

- [ ] **Step 2: Run scraper tests**

Run the test command from Task 1. Expected: all CivicEngage scraper tests pass.

---

## Task 3: Scraper Selection And Source Run Coverage

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/services/search_service.py`
- Modify: `local-contract-hunter-ai/backend/tests/test_search_service.py`

- [ ] **Step 1: Add scraper selection tests**

Add tests asserting:

- `get_scraper_for_source()` returns `CivicEngageBidScraper` for `https://www.alleganygov.org/bids.aspx`.
- Non-`Bids.aspx` generic sources still return `GenericProcurementScraper`.

- [ ] **Step 2: Implement selection**

In `search_service.py`, import `urlparse` and `CivicEngageBidScraper`. Add helper:

```python
def _is_civicengage_bid_source(source: Source) -> bool:
    path = urlparse(source.url).path.lower()
    return "bids.aspx" in path
```

Then return `CivicEngageBidScraper(**kwargs)` before falling back to `GenericProcurementScraper`.

- [ ] **Step 3: Run search service tests**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_search_service.py tests/test_civicengage_bid_scraper.py -q
```

Expected: pass.

---

## Task 4: Verification And Live Smoke

**Files:**
- Modify only if verification reveals defects in touched files.

- [ ] **Step 1: Run focused backend tests**

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_civicengage_bid_scraper.py tests/test_generic_procurement_scraper.py tests/test_search_service.py tests/test_search_routes.py tests/test_source_runs_routes.py tests/test_sources_routes.py -q
```

Expected: pass.

- [ ] **Step 2: Run full backend tests**

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest -q
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend" && npm run build
```

Expected: pass.

- [ ] **Step 4: Restart backend and smoke validate Allegany**

Restart the local backend with the current code, then run:

```bash
curl -sS --max-time 120 -X POST "http://127.0.0.1:8000/api/search/validate/source" \
  -H "Content-Type: application/json" \
  -d '{"source_name":"Allegany County Bid Postings","auto_score":true}'
```

Expected:

- Response is `ok: true`.
- Diagnostic status is `completed`.
- `source_run_id` is present.
- Candidate count is at least `1` when the live site is reachable.

---

## Self-Review

- Spec coverage:
  - Scraper framework: Task 3.
  - CivicEngage scraper: Tasks 1-2.
  - Source run integration: Task 3 uses existing `execute_search()` history.
  - No frontend changes: Task 4 still builds frontend to catch regressions.
- Placeholder scan: no placeholders or incomplete implementation instructions remain.
- Type consistency:
  - Scraper class is consistently named `CivicEngageBidScraper`.
  - Selection helper is consistently named `_is_civicengage_bid_source`.
