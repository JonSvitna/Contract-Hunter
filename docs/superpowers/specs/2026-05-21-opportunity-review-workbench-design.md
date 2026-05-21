# Opportunity Review Workbench Design

## Purpose

Make the opportunities page usable after large eMMA imports. The app now imports hundreds of rows, so the review experience needs server-side pagination, advanced filters, and predictable sorting instead of loading every opportunity and relying on manual scrolling.

## Scope

This spec covers the opportunity review workbench only:

- Add a paginated opportunity search API.
- Add a lightweight opportunity summary API for dashboard totals.
- Support advanced filters for review, eMMA triage, scoring, and deadlines.
- Support stable sorting with explicit direction.
- Update the opportunities page to use URL query params for filters, sorting, and pagination.
- Keep the dashboard lightweight by fetching a limited page instead of all opportunities.
- Preserve existing status updates, detail pages, scoring, import, and settings behavior.

Out of scope for this pass:

- Editing keywords, business profile, or scoring settings.
- Saved filter presets persisted to a user account or database.
- Bulk status updates.
- Exporting filtered results.
- Infinite scroll.

Settings improvements should follow as a separate spec after the review workbench is in place.

## Current Baseline

`GET /api/opportunities` currently returns every opportunity sorted by newest created date. The dashboard uses this full list for summary cards and top opportunities, and `/opportunities` renders every item at once.

That worked for small test data, but after importing the eMMA workbook the app has 500+ opportunities. Full-list fetching is wasteful, and review requires filtering by fit, status, source state, dates, agency, and BPM ID.

## API Design

Add a new endpoint:

- `GET /api/opportunities/search`

Add a dashboard summary endpoint:

- `GET /api/opportunities/summary`

The existing `GET /api/opportunities` should remain compatible for callers that still expect a raw list.

### Query Parameters

Pagination:

- `page`: one-based page number, default `1`.
- `page_size`: default `25`, allowed range `5` to `100`.

Text and identity filters:

- `q`: case-insensitive search across title, agency, description, source name, and external ID.
- `bpm_id`: exact or partial case-insensitive match against `external_id`.
- `agency`: case-insensitive partial match against agency.
- `source`: exact source name.

Workflow and source filters:

- `status`: one or more user workflow statuses, such as `Saved`, `Watch`, `Pursue`, `Skipped`.
- `recommendation`: one or more score recommendations, such as `Pursue`, `Watch`, `Skip`, `Manual Review`.
- `source_status`: one or more source statuses, such as `Open` or `Closed`.
- `manual_review`: optional boolean.

Date filters:

- `due_from`
- `due_to`
- `created_from`
- `created_to`

Score and confidence filters:

- `min_confidence`
- `max_confidence`
- `min_fit_score`
- `max_fit_score`
- `min_skill_match`
- `min_solo_fit`
- `min_revenue_fit`
- `min_local_fit`
- `max_deadline_risk`
- `max_complexity_risk`

Sorting:

- `sort`: one of `created_at`, `updated_at`, `due_date`, `fit_score`, `agency`, `confidence`, `source_status`.
- `direction`: `asc` or `desc`.

Default sort should be `created_at desc`.

### Response Shape

Return a paginated envelope:

```json
{
  "items": [],
  "total": 526,
  "page": 1,
  "page_size": 25,
  "pages": 22
}
```

`items` should use the existing opportunity read shape, including score data.

### Summary Response

`GET /api/opportunities/summary` should return aggregate counts across all opportunities:

```json
{
  "total": 526,
  "pursue": 12,
  "watch": 48,
  "skipped": 35,
  "manual_review": 18,
  "upcoming_deadlines": 211
}
```

## Backend Behavior

The search route should build a SQLAlchemy query against `Opportunity` and left join `OpportunityScore` when score filtering or score sorting is needed. It should apply filters before count and pagination.

Sorting must be deterministic. If two rows tie on the selected sort field, sort by `Opportunity.id desc` as a secondary order.

Null due dates and missing scores should not break sorting or filtering. For score filters, rows without a score should be excluded only when the relevant score filter is present. For recommendation filters, rows without scores should match `Manual Review`, matching the current UI fallback.

The route should normalize score `next_steps` the same way the existing list/detail endpoints do.

## Frontend Design

Turn `/opportunities` into a client-side review workbench that reads and writes URL query params.

Core sections:

- Header with total result count.
- Text search box for title, agency, description, source name, or BPM ID.
- Quick filter chips:
  - `Pursue`
  - `Watch`
  - `Due soon`
  - `Manual review`
  - `eMMA open`
- Advanced filters panel:
  - Workflow status
  - Score recommendation
  - Source
  - eMMA source status
  - Manual review flag
  - Agency
  - Due date range
  - Created date range
  - Confidence range
  - Fit score range
  - Skill/solo/revenue/local fit minimums
  - Deadline/complexity risk maximums
- Sort controls:
  - Newest
  - Recently updated
  - Due soon
  - Fit score
  - Agency
  - Confidence
- Page size selector.
- Previous/next pagination controls with current page and total pages.
- Active filter chips with clear actions.

The initial page load should default to page `1`, page size `25`, and sort `created_at desc`.

## Dashboard Changes

The dashboard should not fetch all opportunities.

- Use `GET /api/opportunities/summary` for summary cards.
- Use `GET /api/opportunities/search?page=1&page_size=6&sort=fit_score&direction=desc` for top opportunities.
- Keep the raw list endpoint as a compatibility fallback, not as the dashboard's default data source.

## Error Handling

Backend:

- Reject invalid page sizes, dates, booleans, sort fields, and directions with `400`.
- Treat empty string query params as unset.
- Clamp page values to a minimum of `1`.

Frontend:

- Show a loading state while filters fetch.
- Show a clear error if the search API fails.
- Keep the current filters visible when a request fails.
- Reset to page `1` whenever filters or sort change.

## Testing

Backend tests should cover:

- Default pagination returns page metadata and limited items.
- Page two returns the next result set.
- Text search matches title, agency, description, and BPM ID.
- Filters work for status, recommendation, source, source status, manual review, agency, date ranges, confidence, and fit score.
- Sort works for created date, updated date, due date, fit score, agency, and confidence.
- Summary endpoint returns accurate aggregate totals independent of page size.
- Invalid sort and direction return `400`.
- Existing `GET /api/opportunities` still returns the raw list shape.

Frontend validation should cover:

- URL query params drive initial filter state.
- Changing filters updates the URL and fetches page one.
- Pagination changes only the page query param.
- Active filter chips clear the right param.
- Empty results show a useful message.

## Acceptance Criteria

- `/opportunities` no longer fetches every opportunity by default.
- Users can filter by status, recommendation, source, eMMA source status, manual review flag, agency, BPM ID, date ranges, confidence, and fit score.
- Users can sort by newest, recently updated, due soon, fit score, agency, and confidence.
- Users can move between pages and change page size.
- Active filters are visible and removable.
- Dashboard summary cards use aggregate totals and top opportunities fetch a limited page instead of the full list.
- Existing detail pages and status buttons continue to work.

## Future Work

- Add persisted saved filter presets.
- Add bulk actions for selected results.
- Add CSV export for filtered results.
- Add dashboard aggregate metrics endpoint.
- Add settings workbench for keywords, business profile, and scoring rules.
