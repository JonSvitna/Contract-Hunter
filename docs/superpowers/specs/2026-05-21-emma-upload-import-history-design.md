# eMMA Upload Import History Design

## Purpose

Replace the current server-local workbook path import with a browser upload flow that works in production. Each uploaded eMMA public solicitations workbook should be saved as an import run, scanned for new and changed solicitations, and used to keep source-derived opportunity fields current while preserving the user's workflow decisions.

## Scope

This spec covers the first production-ready eMMA workbook import flow:

- Upload `Public_Solicitations.xlsx` from the dashboard instead of typing a filesystem path.
- Persist an import run record for every uploaded workbook.
- Persist per-row import results so repeated uploads can explain what changed.
- Identify eMMA solicitations by stable BPM ID.
- Create new opportunities for new BPM IDs.
- Update existing opportunities when source-derived fields change.
- Track source status changes such as Open to Closed without overwriting the user's workflow status.
- Preserve user-owned workflow fields such as status.
- Keep automatic scoring for newly created opportunities.

Out of scope for this pass:

- Per-opportunity PDF or RFP attachment upload.
- Scheduled automatic downloads from eMMA.
- External object storage.
- A manual review workflow for applying changes one by one.
- Automatic rescoring of changed existing opportunities.

## Current Baseline

The existing dashboard import panel sends a workbook path to `POST /api/import/emma-excel`. That works only when the backend process can read the same local filesystem path. It fails in production because the browser runs on the user's machine while the backend runs inside Railway.

The current importer parses open eMMA workbook rows, creates new `Opportunity` rows, scores new rows, and skips duplicates. Duplicate detection currently uses `opportunity_url` or title, agency, and due date. That prevents duplicate creation, but it cannot reliably update an existing solicitation when the source workbook changes.

## Architecture

The new import flow has three boundaries:

1. The frontend uploads a selected `.xlsx` file as `multipart/form-data`.
2. The backend records an import run, parses the workbook, and compares normalized rows against existing opportunities.
3. The database stores import history, row-level actions, and stable source identity fields on opportunities.

The existing Excel parsing code should be reused and refactored so both tests and the upload route parse workbook bytes through the same normalization path. The path-based import route can remain as a local development convenience for now, but the dashboard should use the upload route.

## Data Model

### Opportunities

Add source identity and freshness fields:

- `external_id`: the stable source ID, such as `BPM056393`.
- `source_status`: the latest status from the eMMA workbook, such as `Open` or `Closed`.
- `last_seen_at`: when this opportunity last appeared in an uploaded source workbook.
- `updated_at`: when the opportunity row was last modified by the app.

The unique source identity should be `(source_name, external_id)` when `external_id` is present. Existing fallback duplicate checks by URL or title should remain for older rows that do not yet have an external ID.

### Import Runs

Add an `import_runs` table:

- `id`
- `source_name`
- `filename`
- `content_type`
- `file_size_bytes`
- `file_sha256`
- `workbook_bytes`
- `uploaded_at`
- `rows_seen`
- `created`
- `updated`
- `unchanged`
- `skipped`
- `scored`
- `status`
- `error_message`

The first pass stores workbook bytes in the database so a run is reproducible without configuring object storage. If workbook size becomes a problem, this field can later be replaced with an object storage key.

### Import Run Items

Add an `import_run_items` table:

- `id`
- `import_run_id`
- `opportunity_id`
- `external_id`
- `row_sha256`
- `action`
- `change_summary`
- `raw_title`
- `raw_agency`
- `raw_due_date`
- `raw_source_status`

`action` should be one of `created`, `updated`, `unchanged`, or `skipped`. `change_summary` should be a compact JSON-compatible payload naming changed source-derived fields.

## Import Behavior

For each workbook row with a BPM ID:

1. Normalize the row into the same opportunity candidate shape used today.
2. Extract and store the BPM ID as `external_id`.
3. Compute a deterministic `row_sha256` from source-derived fields.
4. Look up an existing opportunity by `(source_name, external_id)`.
5. If no match exists and the source status is `Open`, create the opportunity, save an item action of `created`, and score it when auto-score is enabled.
6. If no match exists and the source status is not `Open`, save an item action of `skipped` and do not create a new opportunity.
7. If a match exists and the row hash is unchanged, update `last_seen_at`, save an item action of `unchanged`, and do not alter user workflow fields.
8. If a match exists and source-derived fields changed, update only source-owned fields, update `last_seen_at`, save an item action of `updated`, and preserve status.
9. If a row is invalid or cannot be normalized, save an item action of `skipped` with a clear reason.

Source-owned fields include:

- `title`
- `agency`
- `source_url`
- `opportunity_url`
- `due_date`
- `description_snippet`
- `extraction_confidence`
- `manual_review_needed`
- `source_status`

User-owned fields include:

- `status`

Future user-owned fields such as notes, reminders, or bid decisions should follow the same preservation rule.

## API

Add a production upload endpoint:

- `POST /api/import/emma-excel/upload`
- Request: `multipart/form-data`
  - `file`: required `.xlsx`
  - `auto_score`: optional boolean, default `true`
- Response:
  - `ok`
  - `import_run_id`
  - `source`
  - `filename`
  - `rows_seen`
  - `created`
  - `updated`
  - `unchanged`
  - `skipped`
  - `scored`

Add import history endpoints:

- `GET /api/import/runs`
- `GET /api/import/runs/{id}`

The history endpoints should return enough detail for the dashboard to show recent imports and explain what happened during a selected run.

## Frontend

Replace the dashboard workbook path input with:

- A file picker accepting `.xlsx`.
- A score-new-opportunities checkbox.
- An upload and scan button.
- A summary card showing created, updated, unchanged, skipped, and scored counts.
- A recent import history section showing the most recent runs.

The UI should make it clear that the file is uploaded to the backend, not read from a local path. Errors should be plain-language messages for missing files, wrong file type, invalid workbook columns, and backend parse failures.

## Error Handling

The backend should reject:

- Missing file uploads.
- Non-`.xlsx` filenames.
- Empty files.
- Workbooks missing required eMMA columns.

If parsing fails before any rows are processed, the import run should be saved with `status = failed` and `error_message` populated. If individual rows fail but the workbook can continue, those rows should become skipped items and the run should complete.

## Testing

Backend tests should cover:

- Upload endpoint accepts a valid `.xlsx` file.
- Upload endpoint rejects missing or invalid files.
- First upload creates opportunities and an import run.
- Re-uploading the same workbook records unchanged rows without creating duplicates.
- Re-uploading a workbook with the same BPM ID and changed source fields updates the opportunity.
- Re-uploading a workbook where an existing BPM ID changes source status updates `source_status` while preserving workflow status.
- Updated opportunities preserve existing status.
- New opportunities are scored when auto-score is enabled.
- Import run items record created, updated, unchanged, and skipped actions.

Frontend tests or focused manual validation should cover:

- Selecting a workbook enables upload.
- Upload result counts render correctly.
- Error messages render clearly.
- Recent import history appears after a successful upload.

## Acceptance Criteria

- The deployed Vercel frontend can upload an eMMA `.xlsx` workbook to the Railway backend.
- The backend no longer depends on a user-machine file path for dashboard imports.
- Every upload creates an import run record.
- Re-uploading the same workbook does not create duplicate opportunities.
- Re-uploading a changed solicitation updates source-derived fields for the existing opportunity.
- Re-uploading a solicitation whose eMMA status changed records the new source status without changing the user's workflow status.
- Existing opportunity status is preserved during source updates.
- Newly created opportunities are scored when auto-score is enabled.
- The dashboard displays import counts including created, updated, unchanged, skipped, and scored.
- Recent import history is visible from the dashboard.

## Future Work

- Store workbook files in object storage instead of the database.
- Add per-opportunity document uploads for PDFs and attachments.
- Add scheduled source download and change scans.
- Add rescoring controls for changed existing opportunities.
- Add a detailed import run drill-down page.
