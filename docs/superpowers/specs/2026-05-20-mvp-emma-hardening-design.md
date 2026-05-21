# MVP eMMA Hardening Design

## Purpose

Validate and harden the existing Local Contract Hunter AI MVP around one real Maryland eMMA procurement source. Success means one real eMMA opportunity, not mock fallback data, is extracted, persisted, scored, and visible in the dashboard and detail flow.

## Scope

This spec keeps the existing `local-contract-hunter-ai` scaffold as the baseline:

- FastAPI backend.
- Next.js frontend.
- YAML-driven business profile, keywords, sources, scheduler, and scoring rules.
- SQLAlchemy models with local SQLite persistence.
- Playwright-based scraping and eMMA Excel import.
- Rule-based scoring with optional AI overlay.
- Dashboard, opportunity detail pages, and status workflow.

The first hardening pass focuses on the local MVP pipeline only:

1. Configure a one-source validation path for Maryland eMMA.
2. Import the public eMMA solicitations Excel export until at least one real opportunity can be normalized.
3. Persist extracted opportunities with duplicate prevention.
4. Score newly imported opportunities automatically during the validation flow.
5. Display scored real opportunities in the dashboard and detail page.
6. Document a repeatable validation runbook.

Out of scope:

- Vercel and Railway deployment.
- Scheduled production workers.
- Email digests and alerts.
- AI opportunity summaries.
- PDF/RFP parsing.
- Proposal checklist generation.
- Auth, multi-user support, Stripe billing, CRM expansion, SAM.gov, and subcontractor matching.
- Postgres migration in this pass.

SQLite remains the local MVP database. The implementation should avoid unnecessary SQLite-specific assumptions so a later Postgres migration is straightforward, but Postgres is documented as the next database path rather than included in this scope.

## Existing Baseline

The repository already includes most MVP structure:

- `local-contract-hunter-ai/backend/app/main.py` initializes FastAPI, creates database tables, and registers routes.
- `local-contract-hunter-ai/backend/app/routes/search.py` runs configured active sources, stores opportunities, and prevents duplicates.
- `local-contract-hunter-ai/backend/app/scrapers/emma_scraper.py` handles eMMA public solicitation navigation and truthful browser-check fallback.
- `local-contract-hunter-ai/backend/app/services/emma_excel_import_service.py` imports eMMA public solicitation Excel exports.
- `local-contract-hunter-ai/backend/app/services/scoring_service.py` calculates deterministic fit scores and recommendations.
- `local-contract-hunter-ai/frontend/app/page.tsx` and opportunity pages render dashboard and detail data from the API.
- `local-contract-hunter-ai/config/sources.yaml` already includes Maryland eMMA.

The key risk is that automated eMMA browsing can be stopped by eMMA's browser-check page even when public solicitations do not require account login. The validated primary MVP path is therefore manual eMMA export to Excel followed by local import, while the scraper remains a truthful fallback that reports browser-check/manual-review states.

## Architecture

The hardening pass preserves the existing app architecture and introduces a dedicated eMMA validation boundary:

- Source configuration identifies eMMA as the required validation source.
- A dedicated eMMA Excel importer handles normalized extraction for the validated eMMA MVP path.
- A dedicated eMMA scraper handles page loading, public-solicitation navigation, and truthful browser-check/manual-review fallback.
- The search route persists normalized candidates and records duplicate counts.
- The import route persists normalized workbook rows and records duplicate counts.
- The scoring service assigns recommendation labels and reasoning.
- The frontend reads the same API responses and displays the opportunity, score, source links, due date, status, and manual-review state.

The generic scraper remains available for county, municipal, school, library, and utility sources, but it is not the acceptance target for this spec.

## Components

### Source Controls

The validation flow should be able to run eMMA alone through a narrow one-source validation API path. This avoids editing the main source YAML just to run a validation pass. The result should make it clear how many sources ran and whether eMMA was the source that produced the accepted opportunity.

### eMMA Excel Importer

The primary MVP eMMA path uses the public solicitations Excel export from eMMA. The importer should accept a local `.xlsx` path and normalize open rows with:

- `title`
- `agency`
- `source_name`
- `source_url`
- `opportunity_url`
- `due_date`
- `description_snippet`
- `extraction_confidence`
- `manual_review_needed`

The importer should convert Excel serial dates or native workbook datetimes into normal dates. It should build stable eMMA opportunity links from BPM IDs, skip non-open rows, and score newly created opportunities automatically.

### eMMA Scraper

The eMMA scraper remains a fallback/diagnostic path. It should target the public solicitations page and return normalized candidates with:

- `title`
- `agency`
- `source_name`
- `source_url`
- `opportunity_url`
- `due_date`
- `description_snippet`
- `extraction_confidence`
- `manual_review_needed`

The scraper should prefer real opportunity detail links over broad landing pages. It should include enough diagnostics in failure/manual-review cases to explain whether the page failed to load, eMMA browser-check did not complete, selectors failed, no matching opportunities were found, or due-date parsing was incomplete.

### Persistence

The existing duplicate strategy should be preserved and validated:

- Prefer `opportunity_url` as the primary duplicate key when present.
- Fall back to title, agency, and due date when URL is missing or unstable.
- Re-running the eMMA validation should not create duplicate rows for the same posting.

The SQLite schema can remain managed by SQLAlchemy table creation for the local MVP. A later Postgres migration should introduce explicit migrations and production database configuration.

### Scoring

The validation path should produce a scored dashboard result without relying on manual UI-only scoring. Newly created eMMA opportunities should be scored during the Excel import flow so dashboard acceptance can be checked immediately after the run.

The scoring output should include:

- `fit_score`
- `skill_match`
- `solo_fit`
- `revenue_fit`
- `local_fit`
- `deadline_risk`
- `complexity_risk`
- `past_performance_risk`
- `recommendation`
- `reasoning`
- `next_steps`

Recommendation labels remain:

- Pursue
- Watch
- Skip
- Manual Review

### Frontend

The dashboard and opportunity detail flow should display:

- Real eMMA opportunity title and agency.
- Due date or an explicit unknown state.
- Source and opportunity links.
- Extraction confidence and manual-review state when available.
- Fit score and recommendation.
- Why-this-fits reasoning.
- Status workflow: Saved, Watch, Pursue, Skipped.

The existing pages can be reused unless validation exposes missing fields or unclear states.

## Data Flow

1. Local backend starts and seeds sources from YAML if needed.
2. Local frontend starts and reads from the backend API.
3. The user exports public solicitations from eMMA to Excel.
4. The validation run imports the eMMA Excel file.
5. The importer normalizes open solicitation rows.
6. The backend checks each candidate for duplicates.
7. New candidates are persisted in SQLite.
8. New opportunities are scored during the validation flow.
9. The dashboard lists the scored opportunity.
10. The detail page shows score breakdown, reasoning, links, and status controls.
11. A repeated validation run skips duplicates instead of creating new rows.

## Error Handling

Failures should be visible and truthful:

- If Playwright is unavailable, return a manual-review result that says Playwright is unavailable.
- If eMMA cannot be loaded, return or log a scrape failure reason.
- If eMMA browser-check does not complete, return a manual-review result that names browser-check as the reason.
- If the Excel file is missing, unreadable, or has unexpected columns, return a clear import error.
- If selectors fail, identify that extraction failed rather than inserting mock success data.
- If no matching opportunity exists during the run, record that no live eMMA opportunity met the configured keywords.
- If due-date parsing fails, persist the opportunity with `due_date = null` and lower confidence rather than discarding it.
- If an opportunity is real but incomplete, mark `manual_review_needed = true`.

Mock fallback data may remain useful for development, but it must not count as acceptance for this spec. During validation, mock rows should be disabled or clearly excluded from the success check.

## Testing And Validation

Automated or scripted checks should cover:

- eMMA Excel row normalization.
- eMMA scraper candidate normalization.
- Date parsing for formats seen in eMMA text.
- Excel serial/date conversion for eMMA exports.
- Duplicate prevention across repeated runs.
- Scoring output shape and recommendation bands.
- Opportunity API list/detail responses.
- Status update API behavior.

Manual validation runbook:

1. Start the backend locally.
2. Start the frontend locally.
3. Export public solicitations from eMMA to Excel.
4. Run the eMMA Excel import.
5. Confirm at least one real eMMA opportunity row exists in SQLite.
6. Confirm the row has title, agency, source link, confidence, and manual-review state.
7. Confirm the opportunity was scored during the validation search flow.
8. Open the dashboard and confirm the opportunity appears with recommendation data.
9. Open the detail page and confirm links, score breakdown, reasoning, next steps, and status buttons work.
10. Re-run the search and confirm duplicates are skipped.

Acceptance criteria:

- At least one real Maryland eMMA opportunity from the Excel export is persisted.
- The accepted row is not mock fallback data.
- The accepted row has a title, agency, source link, and extraction confidence.
- The accepted opportunity has a score and recommendation label.
- The dashboard displays the accepted opportunity.
- The detail page displays the accepted opportunity, score details, reasoning, links, and status controls.
- A repeated eMMA run does not create duplicate rows for the same opportunity.
- Any scraper failure produces a clear manual-review/failure state.

## Future Specs

After this MVP validation passes, follow-on specs can address:

- Local county source expansion.
- Postgres migration and production database configuration.
- Vercel/Railway deployment.
- Scheduled worker jobs and daily refresh.
- Daily digest email summaries and high-fit alerts.
- AI summaries, PDF parsing, proposal checklists, and bid/no-bid recommendations.
- Auth, multi-user support, Stripe billing, CRM tracking, SAM.gov, and subcontractor/team matching.
