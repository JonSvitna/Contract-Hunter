from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routes import digest, imports, opportunities, scoring, scheduler, search, source_runs, sources
from app.services.schema_maintenance import ensure_runtime_schema
from app.services.source_service import seed_sources_if_empty, sync_missing_seed_sources


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    db = SessionLocal()
    try:
        seed_sources_if_empty(db)
        sync_missing_seed_sources(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


app.include_router(opportunities.router, prefix=settings.api_prefix)
app.include_router(digest.router, prefix=settings.api_prefix)
app.include_router(imports.router, prefix=settings.api_prefix)
app.include_router(scoring.router, prefix=settings.api_prefix)
app.include_router(scheduler.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(source_runs.router, prefix=settings.api_prefix)
app.include_router(sources.router, prefix=settings.api_prefix)
