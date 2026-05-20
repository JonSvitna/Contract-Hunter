# Local Contract Hunter AI

Private MVP for Sean Murrill (Vulnaguard LLC) to discover and prioritize small local Maryland cybersecurity contract opportunities that a solo consultant can realistically win.

## What this MVP does

- Config-driven source targeting (county, municipal, school, library, utility + eMMA secondary).
- Local search run across active sources.
- Opportunity persistence in SQLite with duplicate prevention.
- Rule-based scoring fallback with optional OpenAI-compatible scoring.
- Status workflow: Saved, Watch, Pursue, Skipped.
- Clean dashboard and detail pages for decision-making.

## What this MVP does not do

- No SAM.gov ingestion.
- No federal contract focus.
- No login automation.
- No CAPTCHA bypass.
- No auto-bid submission.
- No auth or billing.

## Project layout

```text
local-contract-hunter-ai/
  backend/
  frontend/
  config/
  docs/
```

## Quick start

### 1) Backend

```powershell
cd local-contract-hunter-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```powershell
cd local-contract-hunter-ai/frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Core API routes

- `GET /health`
- `GET /api/opportunities`
- `GET /api/opportunities/{id}`
- `PATCH /api/opportunities/{id}/status`
- `POST /api/opportunities/{id}/score`
- `POST /api/search/run`
- `GET /api/search/config`
- `GET /api/scheduler`
- `PATCH /api/scheduler`
- `POST /api/scheduler/toggle`
- `GET /api/sources`
- `POST /api/sources`
- `PATCH /api/sources/{id}`

## Scheduler controls

- Scheduler config is stored in `config/scheduler.yaml`.
- Set `enabled: false` to disable automated worker runs.
- Set `frequency_minutes` to increase or reduce run cadence.
- Settings page includes one-click controls: Turn On/Off, Hourly, 12 hours, Daily.

## Launch guidance: Vercel + Railway

### Railway (backend)

1. Create a Railway project from this repo.
2. Root directory: `local-contract-hunter-ai/backend`.
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Add env vars:
   - `CORS_ORIGINS=https://<your-vercel-domain>`
   - `OPENAI_API_KEY` (optional)
   - `SEARCH_DELAY_SECONDS=2.0`
5. For MVP, SQLite can work with Railway volume storage, but move to Postgres for production reliability.
6. Use `backend/.env.example` as the template for Railway environment variables.

### Vercel (frontend)

1. Import repo into Vercel.
2. Root directory: `local-contract-hunter-ai/frontend`.
3. Framework preset: Next.js.
4. Env var:
   - `NEXT_PUBLIC_API_BASE=https://<your-railway-backend-domain>`
5. Deploy and verify dashboard connectivity.
6. Use `frontend/.env.example` for local and hosted variable parity.

## First-run behavior

- If live scraping yields no new rows, the app inserts a small mock set so dashboard and scoring can be tested immediately.
- Mock rows are clearly marked with manual-review style summaries.

## Safety and compliance

- Respect robots.txt and site terms where applicable.
- Use low-frequency requests and configurable delay.
- Fail gracefully to manual review instead of brittle scraping.
- Avoid CAPTCHA bypass and proxy evasion.

## Future

See [docs/ROADMAP.md](docs/ROADMAP.md) for planned expansion.
