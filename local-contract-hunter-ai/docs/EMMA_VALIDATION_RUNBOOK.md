# eMMA Validation Runbook

## Goal

Prove one real Maryland eMMA opportunity can move through the local MVP pipeline: Excel export import, persist, score, dashboard card, detail page, and duplicate prevention.

## Start Backend

```bash
cd local-contract-hunter-ai/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

## Export eMMA Public Solicitations

In eMMA, open `Sourcing`, then `Public Solicitations`, search or filter as needed, and download the Excel export.

Save the workbook locally. The sample validation workbook is:

```text
docs/superpowers/emma_docs/Public_Solicitations.xlsx
```

## Run eMMA Excel Import

```bash
curl -X POST http://localhost:8000/api/import/emma-excel \
  -H 'Content-Type: application/json' \
  --data '{"path":"/Users/seanm/Documents/GitHub/Contract-Hunter/docs/superpowers/emma_docs/Public_Solicitations.xlsx"}'
```

Successful acceptance response has:

```json
{
  "ok": true,
  "source": "Maryland eMMA",
  "rows_seen": 544,
  "created": 526,
  "duplicates_skipped": 18,
  "scored": 1,
  "mock_fallback_used": false
}
```

`created` and `rows_seen` vary with each eMMA export. `created: 0` is acceptable only when the response shows `duplicates_skipped` after a previous successful import.

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
curl -X POST http://localhost:8000/api/import/emma-excel \
  -H 'Content-Type: application/json' \
  --data '{"path":"/Users/seanm/Documents/GitHub/Contract-Hunter/docs/superpowers/emma_docs/Public_Solicitations.xlsx"}'
```

Expected response after a previous successful run:

```json
{
  "ok": true,
  "source": "Maryland eMMA",
  "created": 0,
  "duplicates_skipped": 544,
  "scored": 0,
  "mock_fallback_used": false
}
```

`duplicates_skipped` should equal the number of importable open rows from the file after a previous successful import.

## Failure State

If the Excel file is missing, unreadable, or has unexpected columns, the import endpoint must return a clear error. Mock fallback rows do not satisfy acceptance.

The scraper endpoint `POST /api/search/validate/emma` remains available as a diagnostic fallback. If eMMA browser-check blocks automated browsing, it must return `mock_fallback_used: false` and a manual-review reason that names browser-check explicitly.
