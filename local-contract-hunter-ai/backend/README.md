# Backend - Local Contract Hunter AI

## Run locally

1. Create a virtual environment.
2. Install dependencies.
3. Install Playwright browser runtime.
4. Start the API.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

## Environment variables

- `DATABASE_URL` (optional): defaults to local SQLite.
- `CORS_ORIGINS` (optional): comma-separated list, defaults to `http://localhost:3000`.
- `OPENAI_API_KEY` (optional): if missing, deterministic rule-based scoring is used.
- `OPENAI_MODEL` (optional): default `gpt-4o-mini`.
- `SEARCH_DELAY_SECONDS` (optional): default `2.0`.

## API

- `GET /health`
- `GET /api/opportunities`
- `GET /api/opportunities/{id}`
- `PATCH /api/opportunities/{id}/status`
- `POST /api/opportunities/{id}/score`
- `POST /api/search/run`
- `GET /api/search/config`
- `GET /api/sources`
- `POST /api/sources`
- `PATCH /api/sources/{id}`