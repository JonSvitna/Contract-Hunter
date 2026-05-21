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
