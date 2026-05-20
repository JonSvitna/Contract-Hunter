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
    if not payload:
        return {
            "enabled": False,
            "frequency_minutes": 1440,
            "max_runs_per_day": 2,
            "jitter_seconds": 30,
            "notes": "Disable by default; can be toggled in app settings.",
        }
    return payload


def save_scheduler_config(config: dict) -> dict:
    path = settings.config_dir / "scheduler.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return config


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
