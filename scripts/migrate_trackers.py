"""Migrate existing JSON tracker files into the new SQLite schema."""

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import database


def migrate_trackers():
    database.init_db()
    user_id = database.get_default_user_id()

    trackers_dir = ROOT / "data" / "trackers"
    if not trackers_dir.exists():
        print("No tracker directory found. Nothing to migrate.")
        return

    migrated_count = 0
    for path in sorted(trackers_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                tracker = json.load(f)
        except Exception as exc:
            print(f"Skipped {path.name}: failed to read file ({exc})")
            continue

        tracker_record = {
            "id": tracker.get("id") or path.stem,
            "user_id": user_id,
            "topic": tracker.get("topic", ""),
            "query": tracker.get("query", ""),
            "frequency": tracker.get("frequency", "weekly"),
            "report_mode": tracker.get("report_mode", "both"),
            "created_at": tracker.get("created_at") or "",
            "last_run": tracker.get("last_run"),
            "last_week": tracker.get("last_week"),
            "status": tracker.get("status", "idle"),
            "signal_count": tracker.get("signal_count", 0),
        }

        if not tracker_record["created_at"]:
            created_ts = path.stat().st_ctime
            tracker_record["created_at"] = datetime.datetime.fromtimestamp(created_ts).isoformat()

        database.create_tracker(tracker_record)
        migrated_count += 1

    print(f"Migrated {migrated_count} tracker(s) to SQLite.")


if __name__ == "__main__":
    migrate_trackers()
