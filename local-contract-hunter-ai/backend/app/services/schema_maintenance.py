from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


OPPORTUNITY_COLUMNS = {
    "external_id": "VARCHAR(255)",
    "source_status": "VARCHAR(100)",
    "updated_at": "TIMESTAMP",
    "last_seen_at": "TIMESTAMP",
}


def ensure_runtime_schema(engine: Engine) -> None:
    """Apply additive schema changes for deployments without migrations."""
    inspector = inspect(engine)
    if not inspector.has_table("opportunities"):
        return

    existing = {column["name"] for column in inspector.get_columns("opportunities")}
    missing = {
        name: ddl_type
        for name, ddl_type in OPPORTUNITY_COLUMNS.items()
        if name not in existing
    }
    if not missing:
        return

    with engine.begin() as connection:
        for name, ddl_type in missing.items():
            connection.execute(text(f"ALTER TABLE opportunities ADD COLUMN {name} {ddl_type}"))
