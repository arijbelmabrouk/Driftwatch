"""
delta/report.py
---------------
Job: save reports to disk and load them back.

Delta reports: data/reports/{topic}/{week_current}_vs_{week_previous}/report.json
Summary reports: data/reports/{topic}/{week_current}_summary/report.json
"""

import os
import json
import datetime
import re

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "reports"
)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', '_', text)


# ── Delta report ──────────────────────────────────────────────────────────────

def save_report(
    topic: str,
    week_current: str,
    week_previous: str,
    report_text: str,
    context: dict = None
) -> str:
    topic_slug  = _slugify(topic)
    report_name = f"{week_current}_vs_{week_previous}"
    report_dir  = os.path.join(REPORTS_DIR, topic_slug, report_name)
    os.makedirs(report_dir, exist_ok=True)

    # Save readable text
    with open(os.path.join(report_dir, "report.txt"), "w", encoding="utf-8") as f:
        f.write(f"DRIFTWATCH DELTA REPORT\n{'='*55}\n")
        f.write(f"Topic   : {topic}\n")
        f.write(f"Period  : {week_previous} → {week_current}\n")
        f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*55}\n\n{report_text}\n\n{'='*55}\n")

    # Save JSON
    json_data = {
        "type":          "delta",
        "topic":         topic,
        "week_current":  week_current,
        "week_previous": week_previous,
        "generated_at":  datetime.datetime.now().isoformat(),
        "report":        report_text,
        "metadata": {
            "new_papers":        len(set(c["title"] for c in context["new"]))        if context and "new" in context else 0,
            "continuing_papers": len(set(c["title"] for c in context["continuing"])) if context and "continuing" in context else 0,
            "dropped_papers":    len(set(c["title"] for c in context["dropped"]))    if context and "dropped" in context else 0,
        }
    }

    with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    return report_dir


def load_report(topic: str, week_current: str, week_previous: str) -> dict | None:
    topic_slug = _slugify(topic)
    json_path  = os.path.join(REPORTS_DIR, topic_slug, f"{week_current}_vs_{week_previous}", "report.json")

    if not os.path.exists(json_path):
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Summary report ────────────────────────────────────────────────────────────

def save_summary(topic: str, week_current: str, report_text: str) -> str:
    """Saves a summary report as JSON so it can be loaded back by the API."""
    topic_slug = _slugify(topic)
    report_dir = os.path.join(REPORTS_DIR, topic_slug, f"{week_current}_summary")
    os.makedirs(report_dir, exist_ok=True)

    json_data = {
        "type":         "summary",
        "topic":        topic,
        "week_current": week_current,
        "generated_at": datetime.datetime.now().isoformat(),
        "report":       report_text,
    }

    with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    return report_dir


def load_summary(topic: str, week_current: str) -> dict | None:
    """Loads a previously saved summary report."""
    topic_slug = _slugify(topic)
    json_path  = os.path.join(REPORTS_DIR, topic_slug, f"{week_current}_summary", "report.json")

    if not os.path.exists(json_path):
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Utilities ─────────────────────────────────────────────────────────────────

def list_reports(topic: str) -> list[str]:
    topic_dir = os.path.join(REPORTS_DIR, _slugify(topic))
    if not os.path.exists(topic_dir):
        return []
    return sorted(os.listdir(topic_dir), reverse=True)