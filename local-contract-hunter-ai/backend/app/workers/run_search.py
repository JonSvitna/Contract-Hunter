from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.routes.search import run_search
from app.services.source_service import load_scheduler_config, save_scheduler_config


def main():
    db = SessionLocal()
    try:
        scheduler = load_scheduler_config()
        today = datetime.now(timezone.utc).date().isoformat()

        if scheduler.get("last_run_day") != today:
            scheduler["last_run_day"] = today
            scheduler["runs_today"] = 0

        if not scheduler.get("enabled", False):
            print({"ok": True, "skipped": True, "reason": "scheduler_disabled"})
            return

        if int(scheduler.get("runs_today", 0)) >= int(scheduler.get("max_runs_per_day", 2)):
            scheduler["last_result"] = "skipped:max_runs_reached_today"
            save_scheduler_config(scheduler)
            print({"ok": True, "skipped": True, "reason": "max_runs_reached_today"})
            return

        last_run_at = scheduler.get("last_run_at")
        if last_run_at:
            try:
                parsed_last = datetime.fromisoformat(last_run_at)
                next_allowed = parsed_last + timedelta(minutes=int(scheduler.get("frequency_minutes", 1440)))
                if datetime.now(timezone.utc) < next_allowed:
                    scheduler["last_result"] = "skipped:too_soon_for_frequency"
                    save_scheduler_config(scheduler)
                    print({
                        "ok": True,
                        "skipped": True,
                        "reason": "too_soon_for_frequency",
                        "next_run_at": next_allowed.isoformat(),
                    })
                    return
            except ValueError:
                pass

        result = run_search(db)  # type: ignore[arg-type]
        scheduler["last_run_at"] = datetime.now(timezone.utc).isoformat()
        scheduler["last_run_day"] = today
        scheduler["runs_today"] = int(scheduler.get("runs_today", 0)) + 1
        scheduler["last_result"] = f"success:created={result.get('created', 0)}"
        save_scheduler_config(scheduler)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
