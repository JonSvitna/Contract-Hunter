# Vercel + Railway Launch Playbook

## Goal

Launch Local Contract Hunter AI as a private internal tool with safe automation controls and low-risk rollout.

## Architecture

- Frontend: Vercel (Next.js)
- Backend: Railway (FastAPI)
- Data: SQLite for MVP, migrate to Postgres later
- Scheduler source of truth: config/scheduler.yaml

## Pre-launch checklist

1. Confirm backend API works locally:
   - GET /health
   - GET /api/scheduler/status
   - POST /api/search/run-now
2. Confirm frontend settings page can:
   - toggle scheduler
   - set frequency + max runs/day
   - run search now and show logs
3. Confirm source list is seeded and active flags are correct.
4. Confirm CORS contains Vercel domain.

## Railway setup

1. Create service rooted at local-contract-hunter-ai/backend.
2. Build using Nixpacks and start command:
   - uvicorn app.main:app --host 0.0.0.0 --port $PORT
3. Set environment variables:
   - CORS_ORIGINS=https://<vercel-domain>
   - OPENAI_API_KEY=<optional>
   - SEARCH_DELAY_SECONDS=2.0
   - CRON_WEBHOOK_TOKEN=<long-random-secret>
4. Keep persistent volume if using SQLite.

## Railway scheduler pattern

Use Railway cron or external ping to call automated worker script at a steady interval (e.g., every 15 minutes). Internal guardrails now enforce:

- scheduler enabled/disabled flag
- frequency_minutes minimum spacing
- max_runs_per_day cap

Recommended cron baseline:

- Trigger every 15 minutes
- Set frequency_minutes to desired effective cadence in app settings

This decouples infrastructure cron frequency from business run frequency.

## Vercel setup

1. Create project rooted at local-contract-hunter-ai/frontend.
2. Set env variable:
   - NEXT_PUBLIC_API_BASE=https://<railway-api-domain>
3. Deploy and verify dashboard + settings connectivity.

## Safe production defaults

- enabled: false until validation complete
- frequency_minutes: 1440 (daily)
- max_runs_per_day: 2
- jitter_seconds: 30

## Go-live sequence

1. Deploy backend to Railway.
2. Deploy frontend to Vercel.
3. Enable scheduler in Settings.
4. Run one manual "Run Search Now" validation.
5. Confirm status endpoint shows expected runs_today and next_run_at.
6. Monitor first 48 hours and adjust frequency conservatively.

## Rollback

If scraping load or data quality issues appear:

1. Toggle scheduler off in Settings.
2. Keep manual run mode only.
3. Lower source set or raise frequency interval before re-enabling.

## Throttle tuning

- Use Settings to reduce per-source max links on unstable sites.
- Increase page timeout only for slow portals that frequently time out.
- Keep defaults conservative and tune high-variance sources individually.
