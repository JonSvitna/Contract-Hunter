# Source Validation Dashboard Design

## Purpose

Give the source list a validation dashboard so each configured source has an observable health record: when it last ran, whether it succeeded, how many candidates it found, how many rows were created or skipped, how many were scored, what failed, and whether the source is mostly producing manual-review fallback rows.

This is Phase 1 of the improvement roadmap. It should make the current Maryland county source pack safer to validate one source at a time without flooding the database or losing diagnostic detail in transient API responses.

## Scope

This spec covers:

- Persist scraper/search run history for configured sources.
- Track per-source last run status, candidate count, created count, duplicate/skipped count, scored count, error message, and manual-review fallback rate.
- Add APIs for source dashboard summaries, source run history, source run detail, and one-source validation.
- Update `/sources` into a validation dashboard with per-source status and an action to validate one source.
- Keep validation mock fallback disabled.
- Keep eMMA Excel import history separate from source scraper run history.
- Add tests for the new run persistence, API responses, and UI states.

Out of scope for this pass:

- Bulk validation from the UI.
- Background job queues or live progress streaming.
- Source-specific scrapers for counties that need custom extraction.
- CAPTCHA, login, anti-bot bypasses, or credentialed portals.
- Editing source config, throttle config, keywords, or scoring settings from the dashboard.
- A full run analytics page with charts.
- Migrating away from the current SQLite/runtime schema approach.

## Current Baseline

Configured sources live in `config/sources.yaml` and are seeded into the `sources` table. Startup now calls both `seed_sources_if_empty(db)` and `sync_missing_seed_sources(db)`, so new county sources are inserted into existing databases without overwriting user-edited rows.

The `Source` model currently stores only source configuration:

- `id`
- `name`
- `url`
- `source_type`
- `active`
- `search_delay_seconds`
- `notes`
- `created_at`
- `updated_at`

The source list route is simple:

- `GET /api/sources` returns all sources ordered by name.
- `POST /api/sources/sync-defaults` inserts missing default sources.
- `PATCH /api/sources/{source_id}` updates source config.

The search routes already support one-source validation:

- `POST /api/search/validate/source` accepts `source_name` and `auto_score`.
- It rejects inactive sources and non-`generic` sources.
- It runs `execute_search()` with `source_name`, `source_type="generic"`, `allow_mock_fallback=False`, and the requested scoring behavior.
- `POST /api/search/validate/emma` validates eMMA with mock fallback disabled.

The search service returns aggregate counts and in-memory diagnostics only:

- `created`
- `duplicates_skipped`
- `sources`
- `scored`
- `mock_fallback_used`
- `diagnostics`, currently containing source name, source type, and candidate count.

There is no persistent record of source validation. After a response is gone, the app cannot answer "when did this source last run?", "did it fail?", "did it only produce a manual-review fallback?", or "which sources still need validation?"

The eMMA upload flow already has persistent `ImportRun` and `ImportRunItem` tables. Those records are workbook-specific: they store filename, content type, file size, file hash, workbook bytes, upload time, row actions, and eMMA row metadata.

## Data Model Decision

Add new `SourceRun` and `SourceRunItem` models. Do not reuse `ImportRun` or `ImportRunItem` for scraper validation.

The alternatives are:

- Reuse `ImportRun` and `ImportRunItem`: this avoids new tables, but it would overload workbook fields like `filename`, `file_sha256`, and `workbook_bytes` for browser scraper runs. It would also mix eMMA file import history with source validation history in confusing APIs.
- Add only a `SourceRun` summary table: this is simpler, but it cannot explain which candidates were created, skipped as duplicates, scored, or flagged for manual review.
- Add `SourceRun` and `SourceRunItem`: this is the recommended Phase 1 design because it preserves a clean boundary between source scraping and workbook imports while keeping enough detail to debug one-source validation.

`ImportRun` remains the source of truth for eMMA workbook uploads. `SourceRun` is the source of truth for scraper/search execution, including one-source validation, manual all-source runs, scheduled runs, cron runs, and eMMA browser validation.

## Backend Data Model

### SourceRun

Add a `source_runs` table:

- `id`
- `source_id`: nullable foreign key to `sources.id`.
- `source_name`: denormalized source name at run time.
- `source_type`: denormalized source type at run time.
- `source_url`: denormalized source URL at run time.
- `run_kind`: `validation`, `manual`, `scheduled`, or `cron`.
- `status`: `running`, `completed`, or `failed`.
- `started_at`
- `finished_at`
- `duration_ms`
- `auto_score`: whether the run attempted scoring for new rows.
- `mock_fallback_allowed`: copied from run options.
- `mock_fallback_used`: true only when the legacy mock fallback path inserts mock candidates.
- `candidates_found`: total candidates returned by the scraper before duplicate filtering.
- `created`: persisted opportunities created during this source run.
- `duplicates_skipped`: candidates skipped because they matched existing opportunities.
- `scored`: created opportunities scored during this source run.
- `manual_review_candidates`: candidates returned by the scraper with `manual_review_needed=true`.
- `manual_review_created`: created opportunities with `manual_review_needed=true`.
- `error_message`: nullable plain-language failure message.

`source_id` should be nullable so old history can remain readable if a source is later deleted. The source identity fields should be denormalized so history still shows what was run even if source config changes.

For Phase 1, dashboard "skipped" counts should be backed by `duplicates_skipped` because current scraper validation only skips duplicate candidates. If future source flows add non-duplicate skip reasons, add a separate `skipped` total then instead of changing the meaning of `duplicates_skipped`.

Derived values should be computed in API response serializers rather than stored:

- `manual_review_fallback_rate = manual_review_candidates / candidates_found`

If the denominator is zero, the rate should be `0.0`. This is a practical fallback proxy for Phase 1 because the generic scraper marks no-match, page-context-only, and graceful failure candidates with `manual_review_needed=true`.

### SourceRunItem

Add a `source_run_items` table:

- `id`
- `source_run_id`
- `opportunity_id`: nullable foreign key to `opportunities.id`.
- `action`: `created`, `duplicate`, `scored`, or `failed`.
- `title`
- `agency`
- `opportunity_url`
- `due_date`
- `extraction_confidence`
- `manual_review_needed`
- `error_message`

One candidate should produce one item with the final candidate action:

- `created` when a new opportunity was inserted and not scored.
- `scored` when a new opportunity was inserted and scoring succeeded.
- `duplicate` when duplicate detection skipped the candidate.
- `failed` when processing that candidate failed but the rest of the source run can continue.

Avoid a separate item action for scoring because the dashboard needs candidate-level outcomes, not an event log. The `scored` summary count on `SourceRun` remains the authoritative scoring count.

## API Endpoints

Keep existing source APIs compatible. Add richer dashboard endpoints under `/api/sources` and keep validation execution under `/api/search`.

### `GET /api/sources/dashboard`

Return every source with its latest run summary.

Response shape:

```json
{
  "items": [
    {
      "id": 1,
      "name": "Howard County Procurement",
      "url": "https://www.howardcountymd.gov/procurement",
      "source_type": "generic",
      "active": true,
      "search_delay_seconds": 2.0,
      "notes": "County source",
      "last_run": {
        "id": 14,
        "run_kind": "validation",
        "status": "completed",
        "started_at": "2026-05-21T19:00:00Z",
        "finished_at": "2026-05-21T19:00:04Z",
        "duration_ms": 4120,
        "candidates_found": 1,
        "created": 0,
        "duplicates_skipped": 1,
        "scored": 0,
        "manual_review_candidates": 1,
        "manual_review_created": 0,
        "manual_review_fallback_rate": 1.0,
        "error_message": null
      }
    }
  ]
}
```

Sources with no history should return `last_run: null`.

### `GET /api/sources/{source_id}/runs`

Return recent runs for one source, newest first.

Query parameters:

- `limit`: default `10`, allowed range `1` to `50`.

The response should be a raw list using the same run summary shape returned as `last_run` by `GET /api/sources/dashboard`.

### `GET /api/source-runs/{run_id}`

Return one run with its candidate-level items.

This endpoint supports a future drill-down panel without loading item details for every source on initial page load.

### `POST /api/search/validate/source`

Keep the existing route and request shape:

```json
{
  "source_name": "Howard County Procurement",
  "auto_score": true
}
```

Enhance the response with `source_run_id` and per-source summary fields:

```json
{
  "ok": true,
  "source_run_id": 14,
  "created": 0,
  "duplicates_skipped": 1,
  "sources": 1,
  "scored": 0,
  "mock_fallback_used": false,
  "diagnostics": [
    {
      "source": "Howard County Procurement",
      "source_type": "generic",
      "candidates": 1,
      "manual_review_candidates": 1,
      "source_run_id": 14,
      "status": "completed"
    }
  ]
}
```

Continue rejecting non-generic sources with `400` and missing/inactive sources with `404`.

### Existing Search Runs

Persist `SourceRun` records from all paths that call `execute_search()`:

- `POST /api/search/run`: `run_kind="manual"`.
- `POST /api/search/run-now`: `run_kind="scheduled"` when it actually executes after scheduler checks pass.
- `POST /api/search/cron-run`: `run_kind="cron"`.
- `POST /api/search/validate/source`: `run_kind="validation"`.
- `POST /api/search/validate/emma`: `run_kind="validation"`.

This keeps last-run data accurate even when runs are started outside the dashboard. If scheduler checks skip execution before `execute_search()` runs, no `SourceRun` should be created because no source was contacted.

The cron route can share scheduler-limit logic, but when it does execute it should pass `run_kind="cron"` so run history distinguishes webhook-triggered runs from UI-triggered scheduled runs.

## Service Flow

Extend `SearchRunOptions` with:

- `run_kind: str = "manual"`
- `persist_run_history: bool = True`

`execute_search()` should still return the aggregate response used by existing routes, but internally it should create one `SourceRun` per source.

Per-source flow:

1. Query active sources using the existing source filters.
2. For each source, create a `SourceRun` with `status="running"`, source identity fields, run kind, scoring setting, and fallback setting.
3. Build the scraper with existing throttle controls.
4. Call `scraper.scrape(source.name, source.url, keywords)`.
5. Set `candidates_found` and `manual_review_candidates`.
6. For each candidate:
   - If it is a duplicate, increment `duplicates_skipped` and write a `SourceRunItem` with `action="duplicate"`.
   - If it is new, create the opportunity, increment `created`, and write a `SourceRunItem` tied to the new opportunity.
   - If `auto_score` is true, score the new opportunity, increment `scored`, and use item action `scored`.
   - If the candidate has `manual_review_needed=true`, increment `manual_review_created` only when it creates a row.
7. Mark the run `completed`, set `finished_at`, and compute `duration_ms`.
8. If scraping a source raises an unhandled exception, mark only that source run `failed`, save `error_message`, and continue to the next source when the run contains multiple sources.
9. Return aggregate counts across all source runs.

The generic scraper currently catches most browser and extraction failures and returns a manual-review fallback candidate. Those should be recorded as completed runs with high manual-review rates, not failed runs. A failed run should mean the service could not complete the source execution path at all.

The legacy `mock_candidates()` fallback should stay disabled for validation routes. If it is used by `POST /api/search/run`, attach the fallback rows to the first source run and set `mock_fallback_used=true` on that run and the aggregate response.

## Frontend UI

Turn `/sources` into a source validation dashboard while keeping the current table shape recognizable.

Header:

- Title: `Source Validation`
- Description explaining that Maryland local sources are primary and eMMA is secondary.
- Summary counts:
  - total sources
  - active sources
  - never run
  - failed last run
  - high manual-review rate

Table columns:

- Source: name, notes, and external link.
- Type: `generic` or `emma`.
- Status: active or paused.
- Last run: relative timestamp or `Never`.
- Run result: completed, failed, or running.
- Candidates: `candidates_found`.
- Created / duplicate skipped / scored: compact count group.
- Manual review: fallback rate and created count.
- Error: short error text when latest run failed.
- Actions: `Validate` for active generic sources.

Validation action behavior:

- `Validate` calls `POST /api/search/validate/source` with the source name and `auto_score=true`.
- Disable the clicked row's button while the request is in flight.
- On success, refresh dashboard data and show the counts returned by the run.
- On failure, show the API error message near the row and keep existing dashboard data visible.

Rows should use simple status cues:

- Never run: neutral.
- Completed with low manual-review fallback rate: normal.
- Completed with `manual_review_fallback_rate >= 0.8` and candidates found: warning.
- Failed last run: error.
- Inactive source: muted.

Do not add bulk actions in this phase. Validating one source at a time is intentional because the county source pack contains many generic pages that may produce manual-review fallback rows.

## Validation Workflow

The intended operator flow is:

1. Open `/sources`.
2. Find a source with `Never` or stale last-run state.
3. Click `Validate`.
4. Review candidates, created/duplicate-skipped/scored counts, and manual-review fallback rate.
5. If the run creates a normal opportunity, open `/opportunities` and inspect the result.
6. If the run creates or returns a manual-review fallback, manually open the source URL before treating it as a real opportunity.
7. Run the same source again when needed to confirm duplicate prevention.
8. Move to the next county source only after the current source is understood.

eMMA browser validation remains available through `POST /api/search/validate/emma`, but the Phase 1 dashboard action should focus on generic local sources. eMMA workbook imports remain handled by the dashboard import panel and `ImportRun` history.

## Error Handling

Backend:

- Return `404` when a requested source does not exist or is inactive.
- Return `400` when `/api/search/validate/source` is asked to validate a non-`generic` source.
- Save failed source runs with `status="failed"`, `finished_at`, `duration_ms`, and a concise `error_message`.
- Continue all-source runs after one source fails so a broken county page does not block the rest of the pack.
- Do not expose stack traces in API responses or persisted error messages.
- Treat scraper-produced manual-review fallback candidates as completed diagnostics, not source run failures.

Frontend:

- Keep the dashboard visible when validation fails.
- Show row-level error messages for validation failures.
- Show a page-level error if dashboard data cannot load.
- Disable only the active row action during validation.
- Refresh dashboard data after successful validation.

## SQLite And Runtime Schema Risk

The app currently relies on `Base.metadata.create_all(bind=engine)` plus `ensure_runtime_schema(engine)` for additive columns on existing SQLite databases. There is no formal migration tool in place.

Adding new `source_runs` and `source_run_items` tables is low risk with `create_all()` because new tables are created automatically. The risk is moderate if the implementation later changes existing table columns or constraints, because SQLite cannot apply many schema changes safely through simple `ALTER TABLE` statements.

For Phase 1:

- Prefer new tables over altering existing `sources`, `opportunities`, or `import_runs`.
- Add the new models to `app.models.__init__` and test imports so `create_all()` sees them.
- If indexes are added through SQLAlchemy model declarations, verify they are created for fresh databases.
- Do not add uniqueness constraints that require backfilling existing data.
- If a future phase needs to alter existing tables heavily, introduce Alembic or a deliberate migration path instead of expanding `ensure_runtime_schema()` indefinitely.

## Testing

Backend tests should cover:

- `execute_search()` creates a completed `SourceRun` for a successful one-source validation.
- Candidate counts, created count, duplicate count, scored count, and manual-review counts are persisted correctly.
- Re-running the same source records duplicates in a second `SourceRun`.
- A scraper-produced manual-review fallback creates a completed run with a high manual-review fallback rate.
- A hard scraper/service exception records a failed `SourceRun` and error message.
- All-source runs continue after one source fails.
- Validation routes include `source_run_id` in the response.
- `GET /api/sources/dashboard` returns sources with latest run summaries and `last_run: null` for never-run sources.
- `GET /api/sources/{source_id}/runs` returns newest runs first and respects `limit`.
- `GET /api/source-runs/{run_id}` returns run items and returns `404` for missing runs.
- Existing source list/create/update/sync routes remain compatible.

Frontend validation should cover:

- `/sources` renders sources with no run history.
- Latest run counts render in the table.
- Failed latest run displays an error state.
- Clicking `Validate` disables only that row, calls the validation API, and refreshes dashboard data.
- Validation API errors render without clearing the table.

Manual validation should cover:

- Validate one known generic county source from the UI.
- Re-run it and confirm duplicate behavior is visible in run history.
- Confirm eMMA upload import history still renders separately and is not mixed with source run history.

## Acceptance Criteria

- `/sources` shows a validation dashboard with every configured source and latest run state.
- Sources that have never been run are clearly marked.
- Active generic sources can be validated one at a time from the UI.
- A validation run persists `SourceRun` history and candidate-level `SourceRunItem` rows.
- Latest run summaries include status, started/finished time, candidates found, created, duplicates skipped, scored, errors, and manual-review fallback rate.
- Validation mock fallback remains disabled.
- Generic scraper manual-review fallback rows are measurable through manual-review counts and rates.
- Existing eMMA import history remains separate and unchanged.
- Existing search route response shapes remain compatible, with only additive fields.
- Backend tests pass for source run persistence and new APIs.
- Frontend build or focused manual UI validation confirms the dashboard works.

## Future Work

- Add a run detail drawer on `/sources` that shows candidate-level `SourceRunItem` rows.
- Add filters for failed, never-run, stale, high manual-review rate, and source type.
- Add bulk validation with concurrency limits after one-source validation is trustworthy.
- Add source-specific extractor profiles for counties that repeatedly produce fallback rows.
- Add source categories such as county, school, library, utility, and portal.
- Add scheduled source freshness reports or digest entries for failed/high-fallback sources.
- Introduce formal migrations if schema changes continue beyond additive tables.
