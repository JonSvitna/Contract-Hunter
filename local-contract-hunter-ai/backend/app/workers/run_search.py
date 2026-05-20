from __future__ import annotations

from app.database import SessionLocal
from app.routes.search import run_search
from app.services.source_service import load_scheduler_config


def main():
    db = SessionLocal()
    try:
        scheduler = load_scheduler_config()
        if not scheduler.get("enabled", False):
            print({"ok": True, "skipped": True, "reason": "scheduler_disabled"})
            return
        result = run_search(db)  # type: ignore[arg-type]
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
