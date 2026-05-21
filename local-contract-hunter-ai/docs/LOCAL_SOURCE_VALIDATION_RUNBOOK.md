# Local Source Validation Runbook

## Goal

Validate one configured county, school, or library procurement source at a time through the local search pipeline with mock fallback disabled.

## Safety Constraints

- Use only public, unauthenticated procurement pages.
- Do not automate credentialed portals, CAPTCHA bypasses, or anti-bot workarounds.
- Validate one source per run so diagnostics and duplicate behavior are easy to interpret.
- Treat manual-review fallback rows as diagnostics, not confirmed opportunities.

## Start Backend

```bash
cd local-contract-hunter-ai/backend
source /tmp/contract-hunter-py311/bin/activate
uvicorn app.main:app --reload --port 8000
```

If the shared venv is unavailable, create a Python 3.11 venv in `/tmp` and install `requirements.txt`.

Health check:

```bash
curl http://localhost:8000/health
```

## Pick A Configured Local Source

List configured sources:

```bash
curl http://localhost:8000/api/sources
```

Use the exact `name` for an active `source_type: generic` source. Current local examples include:

- `Baltimore County Procurement`
- `Howard County Procurement`
- `Baltimore City Public Schools Procurement`
- `Howard County Library System Procurement`

Use `POST /api/search/validate/emma` for eMMA. The local source endpoint intentionally rejects non-generic sources.

## Run One Validation

```bash
curl -X POST http://localhost:8000/api/search/validate/source \
  -H 'Content-Type: application/json' \
  --data '{"source_name":"Howard County Procurement","auto_score":true}'
```

Set `auto_score` to `false` if you only want extraction and duplicate validation:

```bash
curl -X POST http://localhost:8000/api/search/validate/source \
  -H 'Content-Type: application/json' \
  --data '{"source_name":"Howard County Procurement","auto_score":false}'
```

The validation route runs with `mock_fallback_used: false`; mock rows are never inserted by this endpoint.

## Interpret The Response

Successful responses include:

```json
{
  "ok": true,
  "created": 1,
  "duplicates_skipped": 0,
  "sources": 1,
  "scored": 1,
  "mock_fallback_used": false,
  "diagnostics": [{"source": "Howard County Procurement", "source_type": "generic", "candidates": 1}]
}
```

- `created > 0` means one or more candidates were persisted.
- `duplicates_skipped > 0` on a repeat run confirms duplicate prevention.
- `sources` should be `1`; if it is `0`, the source name did not match an active configured source.
- `mock_fallback_used` must remain `false` for local validation.
- `scored` follows `auto_score`; with `auto_score: false`, it should be `0`.

## Manual-Review Fallback

The generic scraper creates a manual-review candidate when it cannot find a keyword-matching opportunity link, when only page-level keyword context is available, or when the local browser scrape fails gracefully.

Manual-review rows usually have:

- `title` like `Manual review needed for <source name>`.
- `opportunity_url` set to the source page.
- `manual_review_needed: true`.
- `description_snippet` containing matched page text or a clear failure reason.

Open the source page manually before treating a fallback row as a real opportunity.

## County, School, And Library Validation Loop

1. Pick one active generic source from `config/sources.yaml` or `/api/sources`.
2. Run `POST /api/search/validate/source` with the exact source name.
3. Inspect `/api/opportunities` for the new row, source URL, manual-review state, and score if enabled.
4. Run the same validation again and confirm duplicate prevention.
5. Move to the next county, school district, or library source only after the current source is understood.

## Troubleshooting

- If Playwright is missing, install backend requirements in the active Python 3.11 venv.
- If the browser is blocked or a source requires login/CAPTCHA, leave it as manual review; do not bypass.
- If a source consistently returns manual-review fallback, inspect the public page and consider a future source-specific extractor.
