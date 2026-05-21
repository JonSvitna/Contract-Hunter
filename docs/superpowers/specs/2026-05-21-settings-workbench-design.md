# Settings Workbench Design

## Purpose

Turn the current settings preview into a working settings workbench for the parts of the system that directly control search and scoring:

- Search keywords.
- Business profile.
- Scoring rules.

The app already lets the user edit scheduler and source throttle settings. This phase keeps those controls and adds structured, validated editing for the remaining YAML-backed settings.

## Current State

Settings UI:

- `local-contract-hunter-ai/frontend/app/settings/page.tsx`
- Scheduler and throttle controls are editable.
- Business profile and keywords are read-only JSON/chip previews.

Backend config loading:

- `local-contract-hunter-ai/backend/app/services/source_service.py`
- `load_keywords()` reads `config/keywords.yaml`.
- `load_business_profile()` reads `config/business_profile.yaml`.
- `load_throttle_config()` and scheduler save functions already write YAML.

Scoring:

- `local-contract-hunter-ai/config/scoring_rules.yaml` exists.
- `local-contract-hunter-ai/backend/app/services/scoring_service.py` currently uses hardcoded positive skills, negative terms, weights, penalties, recommendation bands, and deadline rules.

## Scope

In scope:

- Add backend read/write helpers for keywords, business profile, and scoring rules.
- Add validated API routes for updating those settings.
- Update scoring so `score_opportunity()` uses `scoring_rules.yaml` with defaults.
- Replace read-only settings sections with structured editable UI.
- Keep settings YAML-backed; no database migration.
- Add focused backend and frontend tests where practical.

Out of scope:

- User accounts, roles, or audit trails.
- Database-backed setting versions.
- Raw YAML editor.
- Source editing.
- Scheduler/throttle redesign.
- Automatic rescoring of all existing opportunities after a rules change.

## Backend Design

### Config Helpers

Extend `source_service.py` with save helpers:

- `save_keywords(keywords: list[str]) -> dict`
- `load_scoring_rules() -> dict`
- `save_business_profile(profile: dict) -> dict`
- `save_scoring_rules(rules: dict) -> dict`

YAML write behavior should match the scheduler/throttle helpers:

- Use `settings.config_dir`.
- Use UTF-8.
- Use `yaml.safe_dump(..., sort_keys=False)`.

Keyword normalization:

- Trim whitespace.
- Drop empty values.
- Deduplicate case-insensitively while preserving first occurrence.
- Preserve user order.

### Schemas

Create `local-contract-hunter-ai/backend/app/schemas/settings.py`.

Schemas:

- `KeywordsUpdate`
  - `keywords: list[str]`
  - Each keyword must be non-empty after trimming.
  - Maximum 100 keywords.
- `BusinessProfileUpdate`
  - `name`, `company`, `location`, `profile`: strings.
  - `skills`, `certifications`, `education`, `preferred_work`, `avoid`: list of strings.
  - `target_contract_size`: nested object with `preferred_min`, `preferred_max`, `acceptable_max`.
- `ScoringRulesUpdate`
  - `weights`: `skill_match`, `solo_fit`, `revenue_fit`, `local_fit`.
  - `penalties`: `complexity_factor`.
  - `hard_penalties`: list of strings.
  - `positive_skills`: list of strings.
  - `recommendation_bands`: `pursue_min`, `watch_min`.
  - `deadline_rules`: `expired`, `lt_3_days`, `lt_7_days`.

Validation:

- Numeric weights and factors must be between `0` and `1`.
- Recommendation/deadline values must be between `0` and `100`.
- Contract size numbers must be non-negative and ordered:
  - `preferred_min <= preferred_max <= acceptable_max`.

### API Routes

Use the existing search/config namespace to minimize routing churn:

- `GET /api/search/config`
  - Return:
    - `business_profile`
    - `keywords`
    - `scoring_rules`
    - `throttle`
- `PATCH /api/search/config/keywords`
  - Body: `KeywordsUpdate`
  - Saves `keywords.yaml`.
  - Returns normalized keywords.
- `PATCH /api/search/config/business-profile`
  - Body: `BusinessProfileUpdate`
  - Saves `business_profile.yaml`.
  - Returns saved profile.
- `PATCH /api/search/config/scoring-rules`
  - Body: `ScoringRulesUpdate`
  - Saves `scoring_rules.yaml`.
  - Returns saved rules.

Errors:

- Invalid payloads return FastAPI/Pydantic `422`.
- YAML write failures can surface as `500`.

## Scoring Design

Update `scoring_service.py` so scoring uses config with defaults:

- Load scoring rules with `load_scoring_rules()`.
- Keep hardcoded defaults in code so scoring works if `scoring_rules.yaml` is missing.
- Use `positive_skills` from config if present, otherwise use the current `POSITIVE_SKILLS`.
- Use `hard_penalties` as negative terms if present, otherwise use the current `NEGATIVE_TERMS`.
- Use configured weights for the fit score formula.
- Use configured `complexity_factor`.
- Use configured recommendation bands.
- Use configured deadline rules.

Do not change the AI scoring prompt except to pass the same profile data as today. The deterministic fallback should become configurable first.

## Frontend Design

### Types And API

Update `frontend/lib/types.ts` with:

- `BusinessProfile`
- `TargetContractSize`
- `ScoringRules`
- `SettingsConfig`

Update `frontend/lib/api.ts` with:

- `getConfigPreview(): Promise<SettingsConfig>`
- `updateKeywords(keywords: string[])`
- `updateBusinessProfile(profile: BusinessProfile)`
- `updateScoringRules(rules: ScoringRules)`

### Settings UI

Keep `frontend/app/settings/page.tsx` as the page owner for now. It is already large, but this phase should avoid a broad component split unless implementation becomes hard to review.

Add three editable cards:

1. Keywords
   - Textarea or line-based input.
   - One keyword per line.
   - Save button.
   - Shows normalized saved chips after save.

2. Business Profile
   - Text fields for `name`, `company`, `location`, `profile`.
   - Line-based textareas for list fields.
   - Number inputs for contract size.
   - Save button.

3. Scoring Rules
   - Number inputs for weights and complexity penalty.
   - Number inputs for pursue/watch and deadline thresholds.
   - Line-based textareas for positive skills and hard penalties.
   - Save button.

UI behavior:

- Show a short success message per section after save.
- Show API errors per section.
- Disable only the section being saved, not the entire settings page.
- Preserve scheduler and throttle controls.

## Data Flow

1. Settings page loads `GET /api/search/config`.
2. User edits one section.
3. UI submits only that section to a PATCH endpoint.
4. Backend validates, normalizes, writes YAML, and returns saved data.
5. UI updates local state from the API response.
6. Future searches and scoring calls load the updated YAML.

## Testing

Backend tests:

- Keyword update trims, deduplicates, persists, and reloads.
- Business profile update validates target contract size ordering.
- Scoring rules update validates numeric bounds and persists.
- `GET /api/search/config` includes `scoring_rules`.
- Scoring service uses configured weights and recommendation bands.

Frontend verification:

- TypeScript build passes.
- Settings page can compile with the new types/API methods.

Manual smoke:

- Start backend.
- PATCH keywords with a duplicate and blank entry; verify returned list is normalized.
- PATCH scoring rules with a changed `pursue_min`; score a fixture-like opportunity or run backend tests to confirm recommendation changes.

## Acceptance Criteria

- The settings page can edit and save keywords, business profile, and scoring rules.
- Saved settings persist in existing YAML files.
- Scoring behavior uses the saved scoring rules.
- Scheduler and throttle settings continue working.
- Invalid settings are rejected with validation errors.
- Backend tests and frontend build pass.

## Future Work

- Split settings page into focused components.
- Add settings reset-to-default buttons.
- Add a "rescore existing opportunities" action after scoring changes.
- Add version history or audit log if multiple users begin editing settings.
