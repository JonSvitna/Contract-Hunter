# Maryland County Source Pack Design

## Purpose

Expand Contract Hunter beyond the current small set of local sources by adding a complete Maryland county procurement source pack and making sure existing databases receive the new sources safely.

The app already supports configurable `generic` sources and one-source validation through `/api/search/validate/source`. This pass should use that existing foundation rather than building custom scrapers for every county up front.

## Scope

This spec covers:

- Add public procurement source entries for every Maryland county government.
- Include Baltimore City procurement as a county-equivalent local jurisdiction because it is a major Maryland local buyer.
- Preserve the existing eMMA source and current school/library local sources.
- Add a safe backend sync path that inserts missing default sources into existing databases.
- Avoid overwriting user-edited source names, URLs, active flags, delays, or notes.
- Add tests for source sync behavior and source-pack coverage.
- Document the validation loop for checking each county source one at a time.

Out of scope for this pass:

- Source-specific scrapers for counties with complex portals.
- Automatically bypassing logins, CAPTCHA, bot checks, or procurement portals that block headless browsers.
- Bulk validation UI.
- Editing keywords, business profile, or scoring settings.
- Adding every municipality, school district, library, utility, or state agency.

## Current Baseline

`config/sources.yaml` currently seeds these county-level sources:

- Baltimore County Procurement
- Howard County Procurement
- Anne Arundel County Purchasing
- Harford County Procurement
- Montgomery County Procurement
- Prince George's County Procurement
- Frederick County Procurement
- Carroll County Bids and Proposals

It also seeds:

- Maryland eMMA
- Baltimore City Public Schools Procurement
- Montgomery County Public Schools Procurement
- Howard County Library System Procurement

The backend calls `seed_sources_if_empty(db)` during startup. That only inserts configured sources when the `sources` table is empty. Because deployed or local databases already have source rows, adding new entries to `config/sources.yaml` alone will not add them to existing databases.

## Target County Pack

The target source pack should cover all Maryland counties:

- Allegany County
- Anne Arundel County
- Baltimore County
- Calvert County
- Caroline County
- Carroll County
- Cecil County
- Charles County
- Dorchester County
- Frederick County
- Garrett County
- Harford County
- Howard County
- Kent County
- Montgomery County
- Prince George's County
- Queen Anne's County
- St. Mary's County
- Somerset County
- Talbot County
- Washington County
- Wicomico County
- Worcester County

Also include:

- Baltimore City procurement

Existing county source entries should be reused where they are already reasonable. Missing counties should be added with official county procurement, purchasing, bids, solicitations, or finance/procurement pages. If a county uses a third-party public bid portal, use the public landing page that is stable and safe to open manually.

## Source Entry Rules

Each county source should use:

```yaml
- name: <County Name> Procurement
  url: <official public procurement URL>
  source_type: generic
  active: true
  search_delay_seconds: 2.0
  notes: County source
```

Use a more precise name when the county uses a public label such as `Purchasing`, `Bids and Proposals`, or `Procurement and Contracts`.

Do not remove existing non-county local sources. Do not rename existing sources unless the current name is clearly wrong, because names are used by validation and source-specific throttle overrides.

## Backend Sync Design

Add a new source service function:

```python
def sync_missing_seed_sources(db: Session) -> int:
    ...
```

Behavior:

- Load `config/sources.yaml`.
- For each configured source, check for an existing database source with the same `name`.
- Insert only missing names.
- Do not update existing rows, even if the YAML URL, active flag, delay, or notes differ.
- Commit once after adding all missing rows.
- Return the number of inserted rows.

Startup behavior should call both:

```python
seed_sources_if_empty(db)
sync_missing_seed_sources(db)
```

`seed_sources_if_empty` remains useful for first-run behavior and compatibility. `sync_missing_seed_sources` handles existing databases after the source pack grows.

## Optional API Design

Add an admin-safe endpoint only if it is needed for manual deployment repair:

- `POST /api/sources/sync-defaults`

Response:

```json
{
  "created": 15
}
```

This endpoint should use the same insert-missing-only behavior. It should not update or delete rows. If the app currently has no auth, this endpoint should remain conservative and idempotent.

The startup sync is the primary mechanism; the endpoint is a convenience for local/manual refresh.

## Validation Workflow

Validation should remain one source at a time:

1. Open `/sources` and confirm the new county is present and active.
2. Run `POST /api/search/validate/source` with the exact source name.
3. Inspect the created opportunity or manual-review fallback.
4. Run the validation again to confirm duplicate prevention.
5. If a source consistently produces manual-review fallback, leave it active but document it as needing a future source-specific extractor.

This keeps source expansion controlled and avoids flooding the database with untrusted rows from many different county websites at once.

## Testing

Backend tests should cover:

- `sync_missing_seed_sources` inserts configured sources missing from the database.
- Existing rows are not overwritten when YAML values differ.
- Running sync twice is idempotent.
- The source pack includes every Maryland county and Baltimore City.
- Startup still works when the database already contains some sources.
- Existing source create/update/list routes still work.

Manual validation should cover:

- At least one existing source still validates.
- At least one newly added county source validates.
- Re-running validation skips duplicates.

## Acceptance Criteria

- `config/sources.yaml` includes all Maryland counties and Baltimore City procurement.
- Existing deployments receive missing default sources without wiping user edits.
- New county sources appear on `/sources`.
- One-source validation can be run against any new county source.
- Full backend tests pass.
- Frontend build still passes.

## Future Work

- Add a source validation dashboard with last checked time, candidate count, and last error.
- Add per-source extractor profiles for third-party bid portals.
- Add municipality, school district, library, and utility source packs.
- Add source categories or tags such as `county`, `school`, `library`, `utility`, and `portal`.
