from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import settings
from app.models.source import Source


def _read_yaml(path: Path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_seed_sources() -> list[dict]:
    payload = _read_yaml(settings.config_dir / "sources.yaml")
    return payload.get("sources", [])


def load_keywords() -> list[str]:
    payload = _read_yaml(settings.config_dir / "keywords.yaml")
    return payload.get("keywords", [])


def load_business_profile() -> dict:
    return _read_yaml(settings.config_dir / "business_profile.yaml")


def load_scheduler_config() -> dict:
    payload = _read_yaml(settings.config_dir / "scheduler.yaml")
    defaults = {
        "enabled": False,
        "frequency_minutes": 1440,
        "max_runs_per_day": 2,
        "jitter_seconds": 30,
        "last_run_at": None,
        "last_run_day": None,
        "runs_today": 0,
        "last_result": None,
        "notes": "Disable by default; can be toggled in app settings.",
    }
    if not payload:
        return defaults
    merged = {**defaults, **payload}
    return merged


def save_scheduler_config(config: dict) -> dict:
    path = settings.config_dir / "scheduler.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return config


def load_throttle_config() -> dict:
    payload = _read_yaml(settings.config_dir / "scraper_controls.yaml")
    defaults = {
        "defaults": {
            "max_candidate_links": 120,
            "page_timeout_ms": 20000,
            "body_timeout_ms": 5000,
        },
        "by_source": {},
    }
    if not payload:
        return defaults
    merged = {
        "defaults": {**defaults["defaults"], **payload.get("defaults", {})},
        "by_source": payload.get("by_source", {}),
    }
    return merged


def save_throttle_config(config: dict) -> dict:
    path = settings.config_dir / "scraper_controls.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return config


def get_effective_throttle_for_source(source_name: str) -> dict:
    config = load_throttle_config()
    defaults = config.get("defaults", {})
    source_override = config.get("by_source", {}).get(source_name, {})
    return {**defaults, **source_override}


def seed_sources_if_empty(db: Session) -> int:
    existing = db.query(Source).count()
    if existing > 0:
        return 0

    created = 0
    for source in load_seed_sources():
        row = Source(
            name=source["name"],
            url=source["url"],
            source_type=source.get("source_type", "generic"),
            active=source.get("active", True),
            search_delay_seconds=source.get("search_delay_seconds", settings.search_delay_seconds),
            notes=source.get("notes"),
        )
        db.add(row)
        created += 1
    db.commit()
    return created


def sync_missing_seed_sources(db: Session) -> int:
    created = 0
    existing_names = {name for (name,) in db.query(Source.name).all()}

    for source in load_seed_sources():
        if source["name"] in existing_names:
            continue
        row = Source(
            name=source["name"],
            url=source["url"],
            source_type=source.get("source_type", "generic"),
            active=source.get("active", True),
            search_delay_seconds=source.get("search_delay_seconds", settings.search_delay_seconds),
            notes=source.get("notes"),
        )
        db.add(row)
        existing_names.add(source["name"])
        created += 1

    if created:
        db.commit()
    return created
