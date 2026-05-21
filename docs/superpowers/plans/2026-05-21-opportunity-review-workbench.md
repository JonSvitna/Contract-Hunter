# Opportunity Review Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side pagination, advanced filtering, sorting, and dashboard-safe aggregate counts for opportunity review.

**Architecture:** Keep the existing raw `GET /api/opportunities` endpoint compatible, and add new `GET /api/opportunities/search` and `GET /api/opportunities/summary` endpoints. Move query construction into a focused backend service so route code stays small and tests can cover filtering/sorting behavior. Convert `/opportunities` into a client-side workbench that uses URL query params, while the dashboard fetches a limited top-opportunities page plus aggregate summary counts.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic, pytest, Next.js App Router, React client components, TypeScript, Tailwind CSS.

---

## File Structure

- Create `local-contract-hunter-ai/backend/app/services/opportunity_query_service.py`: builds filtered, sorted, paginated queries and dashboard summary counts.
- Modify `local-contract-hunter-ai/backend/app/schemas/opportunity.py`: add paginated response, search parameter, and summary schemas.
- Modify `local-contract-hunter-ai/backend/app/routes/opportunities.py`: add `/search` and `/summary` routes before `/{opportunity_id}`.
- Create `local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py`: route-level tests for pagination, filters, sorting, summary, invalid params, and raw endpoint compatibility.
- Modify `local-contract-hunter-ai/frontend/lib/types.ts`: add `OpportunitySearchResult`, `OpportunitySearchParams`, and `OpportunitySummary`.
- Modify `local-contract-hunter-ai/frontend/lib/api.ts`: add search-query serialization, `searchOpportunities`, and `getOpportunitySummary`.
- Create `local-contract-hunter-ai/frontend/components/OpportunityReviewWorkbench.tsx`: client-side filter/sort/pagination UI.
- Modify `local-contract-hunter-ai/frontend/app/opportunities/page.tsx`: render the workbench instead of fetching all opportunities server-side.
- Modify `local-contract-hunter-ai/frontend/components/DashboardSummary.tsx`: accept aggregate summary counts instead of deriving from a full list.
- Modify `local-contract-hunter-ai/frontend/app/page.tsx`: fetch summary and top six opportunities through new endpoints.

Do not create git commits during implementation unless the user explicitly requests commits.

---

## Task 1: Backend Search Service And Schemas

**Files:**
- Create: `local-contract-hunter-ai/backend/app/services/opportunity_query_service.py`
- Modify: `local-contract-hunter-ai/backend/app/schemas/opportunity.py`

- [ ] **Step 1: Add backend schemas**

In `local-contract-hunter-ai/backend/app/schemas/opportunity.py`, add imports:

```python
from pydantic import BaseModel, Field
```

Keep the existing `OpportunityRead` and `OpportunityStatusUpdate`, then add:

```python
class OpportunitySearchResult(BaseModel):
    items: list[OpportunityRead]
    total: int
    page: int
    page_size: int
    pages: int


class OpportunitySummary(BaseModel):
    total: int
    pursue: int
    watch: int
    skipped: int
    manual_review: int
    upcoming_deadlines: int
```

- [ ] **Step 2: Create the query service skeleton**

Create `local-contract-hunter-ai/backend/app/services/opportunity_query_service.py`:

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore


VALID_SORTS = {
    "created_at",
    "updated_at",
    "due_date",
    "fit_score",
    "agency",
    "confidence",
    "source_status",
}
VALID_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True)
class OpportunitySearchParams:
    page: int = 1
    page_size: int = 25
    q: str | None = None
    bpm_id: str | None = None
    agency: str | None = None
    source: str | None = None
    status: tuple[str, ...] = ()
    recommendation: tuple[str, ...] = ()
    source_status: tuple[str, ...] = ()
    manual_review: bool | None = None
    due_from: date | None = None
    due_to: date | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    min_fit_score: int | None = None
    max_fit_score: int | None = None
    min_skill_match: int | None = None
    min_solo_fit: int | None = None
    min_revenue_fit: int | None = None
    min_local_fit: int | None = None
    max_deadline_risk: int | None = None
    max_complexity_risk: int | None = None
    sort: str = "created_at"
    direction: str = "desc"
```

- [ ] **Step 3: Add normalization helpers**

Append to `opportunity_query_service.py`:

```python
def split_multi(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    result: list[str] = []
    for value in values:
        for part in value.split(","):
            stripped = part.strip()
            if stripped:
                result.append(stripped)
    return tuple(result)


def normalize_score_next_steps(opportunity: Opportunity) -> None:
    if opportunity.score and isinstance(opportunity.score.next_steps, str):
        try:
            opportunity.score.next_steps = json.loads(opportunity.score.next_steps)
        except Exception:
            opportunity.score.next_steps = []


def normalize_score_next_steps_for_many(opportunities: list[Opportunity]) -> list[Opportunity]:
    for opportunity in opportunities:
        normalize_score_next_steps(opportunity)
    return opportunities


def _validate_params(params: OpportunitySearchParams) -> None:
    if params.page_size < 5 or params.page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 5 and 100")
    if params.sort not in VALID_SORTS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {sorted(VALID_SORTS)}")
    if params.direction not in VALID_DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction must be asc or desc")
```

- [ ] **Step 4: Implement filter application**

Append:

```python
def _score_filters_present(params: OpportunitySearchParams) -> bool:
    return any(
        value is not None
        for value in (
            params.min_fit_score,
            params.max_fit_score,
            params.min_skill_match,
            params.min_solo_fit,
            params.min_revenue_fit,
            params.min_local_fit,
            params.max_deadline_risk,
            params.max_complexity_risk,
        )
    ) or bool(params.recommendation)


def _base_query(db: Session, params: OpportunitySearchParams):
    query = db.query(Opportunity).options(joinedload(Opportunity.score))
    if _score_filters_present(params) or params.sort == "fit_score":
        query = query.outerjoin(OpportunityScore)

    if params.q:
        pattern = f"%{params.q}%"
        query = query.filter(
            or_(
                Opportunity.title.ilike(pattern),
                Opportunity.agency.ilike(pattern),
                Opportunity.description_snippet.ilike(pattern),
                Opportunity.source_name.ilike(pattern),
                Opportunity.external_id.ilike(pattern),
            )
        )
    if params.bpm_id:
        query = query.filter(Opportunity.external_id.ilike(f"%{params.bpm_id}%"))
    if params.agency:
        query = query.filter(Opportunity.agency.ilike(f"%{params.agency}%"))
    if params.source:
        query = query.filter(Opportunity.source_name == params.source)
    if params.status:
        query = query.filter(Opportunity.status.in_(params.status))
    if params.source_status:
        query = query.filter(Opportunity.source_status.in_(params.source_status))
    if params.manual_review is not None:
        query = query.filter(Opportunity.manual_review_needed.is_(params.manual_review))
    if params.due_from:
        query = query.filter(Opportunity.due_date >= params.due_from)
    if params.due_to:
        query = query.filter(Opportunity.due_date <= params.due_to)
    if params.created_from:
        query = query.filter(Opportunity.created_at >= params.created_from)
    if params.created_to:
        query = query.filter(Opportunity.created_at <= params.created_to)
    if params.min_confidence is not None:
        query = query.filter(Opportunity.extraction_confidence >= params.min_confidence)
    if params.max_confidence is not None:
        query = query.filter(Opportunity.extraction_confidence <= params.max_confidence)
    if params.recommendation:
        if "Manual Review" in params.recommendation:
            non_manual = tuple(item for item in params.recommendation if item != "Manual Review")
            if non_manual:
                query = query.filter(or_(OpportunityScore.recommendation.in_(non_manual), OpportunityScore.id.is_(None)))
            else:
                query = query.filter(or_(OpportunityScore.recommendation == "Manual Review", OpportunityScore.id.is_(None)))
        else:
            query = query.filter(OpportunityScore.recommendation.in_(params.recommendation))
    if params.min_fit_score is not None:
        query = query.filter(OpportunityScore.fit_score >= params.min_fit_score)
    if params.max_fit_score is not None:
        query = query.filter(OpportunityScore.fit_score <= params.max_fit_score)
    if params.min_skill_match is not None:
        query = query.filter(OpportunityScore.skill_match >= params.min_skill_match)
    if params.min_solo_fit is not None:
        query = query.filter(OpportunityScore.solo_fit >= params.min_solo_fit)
    if params.min_revenue_fit is not None:
        query = query.filter(OpportunityScore.revenue_fit >= params.min_revenue_fit)
    if params.min_local_fit is not None:
        query = query.filter(OpportunityScore.local_fit >= params.min_local_fit)
    if params.max_deadline_risk is not None:
        query = query.filter(OpportunityScore.deadline_risk <= params.max_deadline_risk)
    if params.max_complexity_risk is not None:
        query = query.filter(OpportunityScore.complexity_risk <= params.max_complexity_risk)
    return query
```

- [ ] **Step 5: Implement sorting, search, and summary**

Append:

```python
def _sort_expression(sort: str):
    if sort == "fit_score":
        return OpportunityScore.fit_score
    if sort == "agency":
        return Opportunity.agency
    if sort == "confidence":
        return Opportunity.extraction_confidence
    if sort == "source_status":
        return Opportunity.source_status
    if sort == "due_date":
        return Opportunity.due_date
    if sort == "updated_at":
        return Opportunity.updated_at
    return Opportunity.created_at


def search_opportunities(db: Session, params: OpportunitySearchParams) -> dict:
    _validate_params(params)
    page = max(1, params.page)
    query = _base_query(db, params)
    total = query.count()
    sort_expression = _sort_expression(params.sort)
    ordered = desc(sort_expression) if params.direction == "desc" else asc(sort_expression)
    items = (
        query.order_by(ordered, Opportunity.id.desc())
        .offset((page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return {
        "items": normalize_score_next_steps_for_many(items),
        "total": total,
        "page": page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if total else 0,
    }


def opportunity_summary(db: Session) -> dict:
    today = date.today()
    total = db.query(func.count(Opportunity.id)).scalar() or 0
    pursue = (
        db.query(func.count(Opportunity.id))
        .join(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(OpportunityScore.recommendation == "Pursue")
        .scalar()
        or 0
    )
    watch = (
        db.query(func.count(Opportunity.id))
        .join(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(OpportunityScore.recommendation == "Watch")
        .scalar()
        or 0
    )
    skipped = db.query(func.count(Opportunity.id)).filter(Opportunity.status == "Skipped").scalar() or 0
    manual_review = (
        db.query(func.count(Opportunity.id))
        .outerjoin(OpportunityScore, OpportunityScore.opportunity_id == Opportunity.id)
        .filter(or_(OpportunityScore.recommendation == "Manual Review", OpportunityScore.id.is_(None), Opportunity.manual_review_needed.is_(True)))
        .scalar()
        or 0
    )
    upcoming_deadlines = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.due_date.isnot(None), Opportunity.due_date >= today)
        .scalar()
        or 0
    )
    return {
        "total": total,
        "pursue": pursue,
        "watch": watch,
        "skipped": skipped,
        "manual_review": manual_review,
        "upcoming_deadlines": upcoming_deadlines,
    }
```

- [ ] **Step 6: Verify imports compile**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" - <<'PY'
from app.services.opportunity_query_service import OpportunitySearchParams, search_opportunities, opportunity_summary
print(OpportunitySearchParams())
print(search_opportunities.__name__, opportunity_summary.__name__)
PY
```

Expected: prints an `OpportunitySearchParams(...)` object and function names without import errors.

---

## Task 2: Backend Routes And Tests

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/routes/opportunities.py`
- Create: `local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py`

- [ ] **Step 1: Write route tests**

Create `local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.score import OpportunityScore
from app.routes import opportunities


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(opportunities.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def add_opportunity(
    db_session,
    title: str,
    agency: str = "Maryland Department of Test",
    status: str = "Saved",
    source_name: str = "Maryland eMMA",
    source_status: str = "Open",
    external_id: str | None = None,
    due_date: date | None = None,
    confidence: float = 0.9,
    manual_review: bool = False,
    recommendation: str | None = None,
    fit_score: int = 0,
    skill_match: int = 0,
    created_at: datetime | None = None,
):
    row = Opportunity(
        title=title,
        agency=agency,
        source_name=source_name,
        source_url="https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/rfp/request_browse_public",
        external_id=external_id,
        source_status=source_status,
        due_date=due_date,
        description_snippet=f"{title} description",
        status=status,
        extraction_confidence=confidence,
        manual_review_needed=manual_review,
        created_at=created_at or datetime.utcnow(),
        updated_at=created_at or datetime.utcnow(),
    )
    db_session.add(row)
    db_session.flush()
    if recommendation:
        db_session.add(
            OpportunityScore(
                opportunity_id=row.id,
                fit_score=fit_score,
                skill_match=skill_match,
                solo_fit=70,
                revenue_fit=70,
                local_fit=80,
                deadline_risk=20,
                complexity_risk=30,
                past_performance_risk="Low",
                recommendation=recommendation,
                reasoning=f"{recommendation} reasoning",
                next_steps='["Review posting"]',
            )
        )
    db_session.commit()
    db_session.refresh(row)
    return row
```

Append tests:

```python
def test_search_opportunities_paginates_results(db_session):
    base = datetime(2026, 1, 1)
    for idx in range(6):
        add_opportunity(db_session, title=f"Opportunity {idx}", external_id=f"BPM{idx:06d}", created_at=base + timedelta(days=idx))

    response = make_client(db_session).get("/api/opportunities/search?page=2&page_size=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert payload["pages"] == 3
    assert len(payload["items"]) == 2
```

```python
def test_search_opportunities_filters_text_bpm_status_recommendation_and_source(db_session):
    add_opportunity(db_session, title="Cyber Risk Assessment", external_id="BPM056393", status="Pursue", source_status="Open", recommendation="Pursue", fit_score=91)
    add_opportunity(db_session, title="Road Salt Supplies", external_id="BPM000001", status="Saved", source_status="Closed", recommendation="Skip", fit_score=12)

    response = make_client(db_session).get(
        "/api/opportunities/search",
        params={
            "q": "cyber",
            "bpm_id": "56393",
            "status": "Pursue",
            "recommendation": "Pursue",
            "source_status": "Open",
            "source": "Maryland eMMA",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["external_id"] == "BPM056393"
```

```python
def test_search_opportunities_filters_manual_review_agency_dates_and_scores(db_session):
    add_opportunity(
        db_session,
        title="Manual Cyber Assessment",
        agency="Howard County",
        external_id="BPM111111",
        due_date=date(2026, 6, 1),
        confidence=0.95,
        manual_review=True,
        recommendation="Manual Review",
        fit_score=70,
        skill_match=85,
    )
    add_opportunity(
        db_session,
        title="Low Fit Work",
        agency="Baltimore County",
        external_id="BPM222222",
        due_date=date(2026, 8, 1),
        confidence=0.5,
        manual_review=False,
        recommendation="Watch",
        fit_score=50,
        skill_match=55,
    )

    response = make_client(db_session).get(
        "/api/opportunities/search",
        params={
            "manual_review": "true",
            "agency": "Howard",
            "due_from": "2026-05-01",
            "due_to": "2026-07-01",
            "min_confidence": "0.9",
            "min_fit_score": "65",
            "min_skill_match": "80",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["agency"] == "Howard County"
```

```python
def test_search_opportunities_sorts_by_fit_score_desc(db_session):
    add_opportunity(db_session, title="Low Fit", external_id="BPM1", recommendation="Watch", fit_score=40)
    add_opportunity(db_session, title="High Fit", external_id="BPM2", recommendation="Pursue", fit_score=95)

    response = make_client(db_session).get("/api/opportunities/search?sort=fit_score&direction=desc")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["High Fit", "Low Fit"]
```

```python
def test_opportunity_summary_returns_aggregate_counts(db_session):
    add_opportunity(db_session, title="Pursue Work", status="Saved", recommendation="Pursue", due_date=date(2099, 1, 1))
    add_opportunity(db_session, title="Watch Work", status="Saved", recommendation="Watch", due_date=date(2099, 2, 1))
    add_opportunity(db_session, title="Skipped Work", status="Skipped", recommendation="Skip", due_date=date(2020, 1, 1))
    add_opportunity(db_session, title="Unscored Work", status="Saved", manual_review=True)

    response = make_client(db_session).get("/api/opportunities/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["pursue"] == 1
    assert payload["watch"] == 1
    assert payload["skipped"] == 1
    assert payload["manual_review"] >= 1
    assert payload["upcoming_deadlines"] == 2
```

```python
def test_search_opportunities_rejects_invalid_sort_and_keeps_raw_list_compatible(db_session):
    add_opportunity(db_session, title="Raw List")

    bad = make_client(db_session).get("/api/opportunities/search?sort=unknown")
    raw = make_client(db_session).get("/api/opportunities")

    assert bad.status_code == 400
    assert raw.status_code == 200
    assert isinstance(raw.json(), list)
    assert raw.json()[0]["title"] == "Raw List"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py" -q
```

Expected: fails with 404 for `/api/opportunities/search` and `/api/opportunities/summary`.

- [ ] **Step 3: Wire routes**

Modify imports in `local-contract-hunter-ai/backend/app/routes/opportunities.py`:

```python
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
```

Add schema and service imports:

```python
from app.schemas.opportunity import (
    OpportunityRead,
    OpportunitySearchResult,
    OpportunityStatusUpdate,
    OpportunitySummary,
)
from app.services.opportunity_query_service import (
    OpportunitySearchParams,
    normalize_score_next_steps,
    normalize_score_next_steps_for_many,
    opportunity_summary,
    search_opportunities,
    split_multi,
)
```

In `list_opportunities`, replace the local next_steps loop with:

```python
    return normalize_score_next_steps_for_many(opportunities)
```

Add these routes before `@router.get("/{opportunity_id}")`:

```python
@router.get("/search", response_model=OpportunitySearchResult)
def search_opportunities_route(
    page: int = Query(default=1),
    page_size: int = Query(default=25),
    q: str | None = None,
    bpm_id: str | None = None,
    agency: str | None = None,
    source: str | None = None,
    status: Annotated[list[str] | None, Query()] = None,
    recommendation: Annotated[list[str] | None, Query()] = None,
    source_status: Annotated[list[str] | None, Query()] = None,
    manual_review: bool | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    min_fit_score: int | None = None,
    max_fit_score: int | None = None,
    min_skill_match: int | None = None,
    min_solo_fit: int | None = None,
    min_revenue_fit: int | None = None,
    min_local_fit: int | None = None,
    max_deadline_risk: int | None = None,
    max_complexity_risk: int | None = None,
    sort: str = "created_at",
    direction: str = "desc",
    db: Session = Depends(get_db),
):
    params = OpportunitySearchParams(
        page=page,
        page_size=page_size,
        q=q.strip() if q else None,
        bpm_id=bpm_id.strip() if bpm_id else None,
        agency=agency.strip() if agency else None,
        source=source.strip() if source else None,
        status=split_multi(status),
        recommendation=split_multi(recommendation),
        source_status=split_multi(source_status),
        manual_review=manual_review,
        due_from=due_from,
        due_to=due_to,
        created_from=created_from,
        created_to=created_to,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_fit_score=min_fit_score,
        max_fit_score=max_fit_score,
        min_skill_match=min_skill_match,
        min_solo_fit=min_solo_fit,
        min_revenue_fit=min_revenue_fit,
        min_local_fit=min_local_fit,
        max_deadline_risk=max_deadline_risk,
        max_complexity_risk=max_complexity_risk,
        sort=sort,
        direction=direction,
    )
    return search_opportunities(db, params)


@router.get("/summary", response_model=OpportunitySummary)
def get_opportunity_summary(db: Session = Depends(get_db)):
    return opportunity_summary(db)
```

In `get_opportunity`, replace the local score normalizer with:

```python
    normalize_score_next_steps(opp)
```

- [ ] **Step 4: Run route tests**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py" -q
```

Expected: all tests in the file pass.

---

## Task 3: Frontend Types And API Client

**Files:**
- Modify: `local-contract-hunter-ai/frontend/lib/types.ts`
- Modify: `local-contract-hunter-ai/frontend/lib/api.ts`

- [ ] **Step 1: Add frontend types**

In `local-contract-hunter-ai/frontend/lib/types.ts`, after `Opportunity`, add:

```typescript
export type OpportunitySearchParams = {
  page?: number;
  page_size?: number;
  q?: string;
  bpm_id?: string;
  agency?: string;
  source?: string;
  status?: string[];
  recommendation?: string[];
  source_status?: string[];
  manual_review?: boolean;
  due_from?: string;
  due_to?: string;
  created_from?: string;
  created_to?: string;
  min_confidence?: number;
  max_confidence?: number;
  min_fit_score?: number;
  max_fit_score?: number;
  min_skill_match?: number;
  min_solo_fit?: number;
  min_revenue_fit?: number;
  min_local_fit?: number;
  max_deadline_risk?: number;
  max_complexity_risk?: number;
  sort?: string;
  direction?: "asc" | "desc";
};

export type OpportunitySearchResult = {
  items: Opportunity[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type OpportunitySummary = {
  total: number;
  pursue: number;
  watch: number;
  skipped: number;
  manual_review: number;
  upcoming_deadlines: number;
};
```

- [ ] **Step 2: Add API methods**

Update imports in `local-contract-hunter-ai/frontend/lib/api.ts`:

```typescript
  OpportunitySearchParams,
  OpportunitySearchResult,
  OpportunitySummary,
```

Add a query-string helper above `export const api`:

```typescript
function toQueryString(params: OpportunitySearchParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((item) => search.append(key, item));
      return;
    }
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}
```

Add API methods:

```typescript
  searchOpportunities: (params: OpportunitySearchParams = {}) =>
    fetchJson<OpportunitySearchResult>(`/api/opportunities/search${toQueryString(params)}`),
  getOpportunitySummary: () => fetchJson<OpportunitySummary>("/api/opportunities/summary"),
```

- [ ] **Step 3: Run TypeScript build**

Run:

```bash
cd /Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend && npm run build
```

Expected: build passes.

---

## Task 4: Opportunity Review Workbench UI

**Files:**
- Create: `local-contract-hunter-ai/frontend/components/OpportunityReviewWorkbench.tsx`
- Modify: `local-contract-hunter-ai/frontend/app/opportunities/page.tsx`

- [ ] **Step 1: Create the workbench component**

Create `local-contract-hunter-ai/frontend/components/OpportunityReviewWorkbench.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { OpportunityCard } from "@/components/OpportunityCard";
import { api } from "@/lib/api";
import { OpportunitySearchParams, OpportunitySearchResult } from "@/lib/types";

const STATUS_OPTIONS = ["Saved", "Watch", "Pursue", "Skipped"];
const RECOMMENDATION_OPTIONS = ["Pursue", "Watch", "Skip", "Manual Review"];
const SORT_OPTIONS = [
  { label: "Newest", sort: "created_at", direction: "desc" },
  { label: "Recently updated", sort: "updated_at", direction: "desc" },
  { label: "Due soon", sort: "due_date", direction: "asc" },
  { label: "Fit score", sort: "fit_score", direction: "desc" },
  { label: "Agency", sort: "agency", direction: "asc" },
  { label: "Confidence", sort: "confidence", direction: "desc" },
];

function values(searchParams: URLSearchParams, key: string): string[] {
  return searchParams.getAll(key).flatMap((value) => value.split(",")).map((value) => value.trim()).filter(Boolean);
}

function numberValue(searchParams: URLSearchParams, key: string): number | undefined {
  const raw = searchParams.get(key);
  if (!raw) return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}
```

- [ ] **Step 2: Add state/query parsing**

Append:

```tsx
function paramsFromSearch(searchParams: URLSearchParams): OpportunitySearchParams {
  return {
    page: numberValue(searchParams, "page") || 1,
    page_size: numberValue(searchParams, "page_size") || 25,
    q: searchParams.get("q") || undefined,
    bpm_id: searchParams.get("bpm_id") || undefined,
    agency: searchParams.get("agency") || undefined,
    source: searchParams.get("source") || undefined,
    status: values(searchParams, "status"),
    recommendation: values(searchParams, "recommendation"),
    source_status: values(searchParams, "source_status"),
    manual_review: searchParams.get("manual_review") ? searchParams.get("manual_review") === "true" : undefined,
    due_from: searchParams.get("due_from") || undefined,
    due_to: searchParams.get("due_to") || undefined,
    created_from: searchParams.get("created_from") || undefined,
    created_to: searchParams.get("created_to") || undefined,
    min_confidence: numberValue(searchParams, "min_confidence"),
    max_confidence: numberValue(searchParams, "max_confidence"),
    min_fit_score: numberValue(searchParams, "min_fit_score"),
    max_fit_score: numberValue(searchParams, "max_fit_score"),
    min_skill_match: numberValue(searchParams, "min_skill_match"),
    min_solo_fit: numberValue(searchParams, "min_solo_fit"),
    min_revenue_fit: numberValue(searchParams, "min_revenue_fit"),
    min_local_fit: numberValue(searchParams, "min_local_fit"),
    max_deadline_risk: numberValue(searchParams, "max_deadline_risk"),
    max_complexity_risk: numberValue(searchParams, "max_complexity_risk"),
    sort: searchParams.get("sort") || "created_at",
    direction: (searchParams.get("direction") as "asc" | "desc" | null) || "desc",
  };
}

function cleanParams(params: OpportunitySearchParams): OpportunitySearchParams {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== "";
    })
  ) as OpportunitySearchParams;
}
```

- [ ] **Step 3: Add component behavior**

Append:

```tsx
export function OpportunityReviewWorkbench() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useMemo(() => paramsFromSearch(searchParams), [searchParams]);
  const [draft, setDraft] = useState(params);
  const [result, setResult] = useState<OpportunitySearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(params);
    setLoading(true);
    setError(null);
    api.searchOpportunities(cleanParams(params))
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load opportunities."))
      .finally(() => setLoading(false));
  }, [params]);

  function pushParams(next: OpportunitySearchParams) {
    const cleaned = cleanParams(next);
    const query = new URLSearchParams();
    Object.entries(cleaned).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => query.append(key, item));
      } else {
        query.set(key, String(value));
      }
    });
    router.push(`/opportunities${query.toString() ? `?${query.toString()}` : ""}`);
  }

  function applyFilters() {
    pushParams({ ...draft, page: 1 });
  }

  function clearFilters() {
    pushParams({ page: 1, page_size: draft.page_size || 25, sort: "created_at", direction: "desc" });
  }

  function toggleMulti(key: "status" | "recommendation" | "source_status", value: string) {
    const current = draft[key] || [];
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    setDraft({ ...draft, [key]: next });
  }

  function setPage(page: number) {
    pushParams({ ...params, page });
  }
```

- [ ] **Step 4: Add component markup**

Append inside the component after helpers:

```tsx
  const activeFilters = Object.entries(cleanParams(params)).filter(([key]) => !["page", "page_size", "sort", "direction"].includes(key));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-ink">Opportunities</h2>
          <p className="mt-1 text-sm text-slate-600">
            {result ? `${result.total} matching opportunities` : "Loading opportunities..."}
          </p>
        </div>
        <button onClick={clearFilters} className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700">
          Clear filters
        </button>
      </div>

      <section className="card space-y-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px_180px]">
          <label className="text-sm font-medium text-slate-700">
            Search
            <input
              value={draft.q || ""}
              onChange={(event) => setDraft({ ...draft, q: event.target.value })}
              placeholder="Title, agency, source, description, BPM ID"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Sort
            <select
              value={`${draft.sort || "created_at"}:${draft.direction || "desc"}`}
              onChange={(event) => {
                const [sort, direction] = event.target.value.split(":");
                setDraft({ ...draft, sort, direction: direction as "asc" | "desc" });
              }}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.label} value={`${option.sort}:${option.direction}`}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Page size
            <select
              value={draft.page_size || 25}
              onChange={(event) => setDraft({ ...draft, page_size: Number(event.target.value) })}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>
```

Continue:

```tsx
        <div className="flex flex-wrap gap-2">
          {["Pursue", "Watch"].map((value) => (
            <button key={value} onClick={() => setDraft({ ...draft, recommendation: [value] })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{value}</button>
          ))}
          <button onClick={() => setDraft({ ...draft, due_to: new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10) })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">Due soon</button>
          <button onClick={() => setDraft({ ...draft, manual_review: true })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">Manual review</button>
          <button onClick={() => setDraft({ ...draft, source: "Maryland eMMA", source_status: ["Open"] })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">eMMA open</button>
        </div>

        <details className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink">Advanced filters</summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-xs text-slate-600">BPM ID<input value={draft.bpm_id || ""} onChange={(e) => setDraft({ ...draft, bpm_id: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Agency<input value={draft.agency || ""} onChange={(e) => setDraft({ ...draft, agency: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Source<input value={draft.source || ""} onChange={(e) => setDraft({ ...draft, source: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Due from<input type="date" value={draft.due_from || ""} onChange={(e) => setDraft({ ...draft, due_from: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Due to<input type="date" value={draft.due_to || ""} onChange={(e) => setDraft({ ...draft, due_to: e.target.value })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Min fit score<input type="number" value={draft.min_fit_score ?? ""} onChange={(e) => setDraft({ ...draft, min_fit_score: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max fit score<input type="number" value={draft.max_fit_score ?? ""} onChange={(e) => setDraft({ ...draft, max_fit_score: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Min confidence<input type="number" min="0" max="1" step="0.05" value={draft.min_confidence ?? ""} onChange={(e) => setDraft({ ...draft, min_confidence: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max deadline risk<input type="number" value={draft.max_deadline_risk ?? ""} onChange={(e) => setDraft({ ...draft, max_deadline_risk: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
            <label className="text-xs text-slate-600">Max complexity risk<input type="number" value={draft.max_complexity_risk ?? ""} onChange={(e) => setDraft({ ...draft, max_complexity_risk: e.target.value ? Number(e.target.value) : undefined })} className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm" /></label>
          </div>
```

Continue:

```tsx
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <div>
              <div className="mb-1 text-xs font-medium text-slate-600">Workflow status</div>
              <div className="flex flex-wrap gap-2">
                {STATUS_OPTIONS.map((value) => (
                  <button key={value} onClick={() => toggleMulti("status", value)} className={`rounded-full px-3 py-1 text-xs ${draft.status?.includes(value) ? "bg-navy text-white" : "bg-slate-100 text-slate-700"}`}>{value}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-slate-600">Recommendation</div>
              <div className="flex flex-wrap gap-2">
                {RECOMMENDATION_OPTIONS.map((value) => (
                  <button key={value} onClick={() => toggleMulti("recommendation", value)} className={`rounded-full px-3 py-1 text-xs ${draft.recommendation?.includes(value) ? "bg-navy text-white" : "bg-slate-100 text-slate-700"}`}>{value}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-slate-600">eMMA source status</div>
              <div className="flex flex-wrap gap-2">
                {["Open", "Closed"].map((value) => (
                  <button key={value} onClick={() => toggleMulti("source_status", value)} className={`rounded-full px-3 py-1 text-xs ${draft.source_status?.includes(value) ? "bg-navy text-white" : "bg-slate-100 text-slate-700"}`}>{value}</button>
                ))}
              </div>
            </div>
          </div>
        </details>

        <div className="flex flex-wrap gap-2">
          <button onClick={applyFilters} className="rounded-md bg-navy px-3 py-2 text-sm font-medium text-white">Apply filters</button>
          {activeFilters.map(([key, value]) => (
            <button key={key} onClick={() => pushParams({ ...params, [key]: undefined, page: 1 })} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
              Clear {key}: {Array.isArray(value) ? value.join(", ") : String(value)}
            </button>
          ))}
        </div>
      </section>
```

Finish the component:

```tsx
      {error && <div className="card border-red-200 bg-red-50 text-sm text-red-700">{error}</div>}
      {loading && <div className="card text-sm text-slate-600">Loading opportunities...</div>}
      {!loading && result && (
        <>
          <div className="grid gap-4">
            {result.items.map((item) => <OpportunityCard key={item.id} item={item} />)}
            {result.items.length === 0 && <div className="card text-sm text-slate-600">No opportunities match these filters.</div>}
          </div>
          <div className="card flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
            <button disabled={result.page <= 1} onClick={() => setPage(result.page - 1)} className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-50">Previous</button>
            <span>Page {result.page} of {result.pages || 1}</span>
            <button disabled={result.pages === 0 || result.page >= result.pages} onClick={() => setPage(result.page + 1)} className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-50">Next</button>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Replace the opportunities page**

Modify `local-contract-hunter-ai/frontend/app/opportunities/page.tsx`:

```tsx
import { OpportunityReviewWorkbench } from "@/components/OpportunityReviewWorkbench";

export default function OpportunitiesPage() {
  return <OpportunityReviewWorkbench />;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd /Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend && npm run build
```

Expected: build passes.

---

## Task 5: Dashboard Summary Migration

**Files:**
- Modify: `local-contract-hunter-ai/frontend/components/DashboardSummary.tsx`
- Modify: `local-contract-hunter-ai/frontend/app/page.tsx`

- [ ] **Step 1: Update dashboard summary component**

Replace `local-contract-hunter-ai/frontend/components/DashboardSummary.tsx` with:

```tsx
import { OpportunitySummary } from "@/lib/types";

function stat(label: string, value: number | string) {
  return (
    <div className="card min-h-[96px]">
      <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

export function DashboardSummary({ summary }: { summary: OpportunitySummary | null }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {stat("Total Opportunities", summary?.total ?? 0)}
      {stat("Strong Pursue", summary?.pursue ?? 0)}
      {stat("Watch", summary?.watch ?? 0)}
      {stat("Skipped", summary?.skipped ?? 0)}
      {stat("Manual Review", summary?.manual_review ?? 0)}
      {stat("Upcoming Deadlines", summary?.upcoming_deadlines ?? 0)}
    </div>
  );
}
```

- [ ] **Step 2: Update dashboard data fetching**

Modify `local-contract-hunter-ai/frontend/app/page.tsx`:

```tsx
const topOpportunities = await api.searchOpportunities({
  page: 1,
  page_size: 6,
  sort: "fit_score",
  direction: "desc",
}).catch(() => ({ items: [], total: 0, page: 1, page_size: 6, pages: 0 }));
const opportunitySummary = await api.getOpportunitySummary().catch(() => null);
```

Replace:

```tsx
<DashboardSummary opportunities={opportunities} />
```

with:

```tsx
<DashboardSummary summary={opportunitySummary} />
```

Replace top opportunities mapping:

```tsx
{topOpportunities.items.map((item) => (
  <OpportunityCard key={item.id} item={item} />
))}
{topOpportunities.items.length === 0 && <div className="card text-sm text-slate-600">No opportunities found yet. Run search from your backend endpoint.</div>}
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd /Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend && npm run build
```

Expected: build passes.

---

## Task 6: Full Verification

**Files:**
- Modify only if verification reveals defects in files touched by Tasks 1-5.

- [ ] **Step 1: Run backend route tests**

Run:

```bash
PYTHONPATH="/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" "/tmp/contract-hunter-verify-py311/bin/python" -m pytest "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend/tests/test_opportunity_search_routes.py" -q
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
cd /Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend && npm run build
```

Expected: pass.

- [ ] **Step 4: Smoke-test the new API with an existing local database**

If a backend server is already running on port `8000`, use it. Otherwise start a temporary backend on an unused port with a temp DB and import the sample workbook first.

Run against the active backend:

```bash
curl -sS "http://127.0.0.1:8000/api/opportunities/search?page=1&page_size=10&sort=fit_score&direction=desc"
curl -sS "http://127.0.0.1:8000/api/opportunities/summary"
```

Expected:

- Search response has `items`, `total`, `page`, `page_size`, and `pages`.
- Summary response has `total`, `pursue`, `watch`, `skipped`, `manual_review`, and `upcoming_deadlines`.

- [ ] **Step 5: Manual frontend check**

Open `/opportunities` and verify:

- Initial page loads no more than 25 cards.
- Search by a BPM ID filters results.
- `Pursue` and `Watch` chips filter by recommendation.
- `eMMA open` filters to Maryland eMMA open rows.
- Sort by fit score changes ordering.
- Next/previous pagination changes page.
- Active filter chips clear individual filters.

---

## Self-Review

- Spec coverage:
  - Paginated search endpoint: Tasks 1-2.
  - Summary endpoint: Tasks 1-2 and Task 5.
  - Advanced filters: Tasks 1, 2, and 4.
  - Stable sorting: Tasks 1, 2, and 4.
  - URL query params: Task 4.
  - Dashboard limited fetch and aggregate counts: Task 5.
  - Raw endpoint compatibility: Task 2.
- Placeholder scan: no placeholder tokens or incomplete implementation notes are intentionally left in this plan.
- Type consistency:
  - Backend response `items`, `total`, `page`, `page_size`, `pages` matches frontend `OpportunitySearchResult`.
  - Backend summary fields match frontend `OpportunitySummary`.
  - Query param names match between frontend `OpportunitySearchParams` and backend route parameters.
