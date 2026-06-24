"""
delta/report.py
---------------
Job: save delta reports to disk and load them back.

Reports are saved in two formats:
    - JSON  : machine-readable, for the dashboard later
    - .txt  : human-readable, for quick inspection

Saved under: data/reports/{topic_slug}/{week_current}_vs_{week_previous}/
"""

import os
import json
import datetime
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Reports directory — inside /data which is already gitignored
REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "reports"
)


def _slugify(text: str) -> str:
    """Converts 'Large Language Models' → 'large_language_models'"""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text


def save_report(
    topic: str,
    week_current: str,
    week_previous: str,
    report_text: str,
    context: dict = None
) -> str:
    """
    Saves a delta report to disk in both JSON and text formats.

    Args:
        topic:         plain English topic
        week_current:  e.g. "2026-W25"
        week_previous: e.g. "2026-W24"
        report_text:   the LLM's response string
        context:       optional comparator context for metadata

    Returns:
        Path to the saved report directory.
    """
    # Build directory path
    topic_slug   = _slugify(topic)
    report_name  = f"{week_current}_vs_{week_previous}"
    report_dir   = os.path.join(REPORTS_DIR, topic_slug, report_name)
    os.makedirs(report_dir, exist_ok=True)

    # ── Save as readable text ─────────────────────────────────────────────────
    txt_path = os.path.join(report_dir, "report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"DRIFTWATCH DELTA REPORT\n")
        f.write(f"{'='*55}\n")
        f.write(f"Topic   : {topic}\n")
        f.write(f"Period  : {week_previous} → {week_current}\n")
        f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*55}\n\n")
        f.write(report_text)
        f.write(f"\n\n{'='*55}\n")

    # ── Save as JSON ──────────────────────────────────────────────────────────
    json_data = {
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

    json_path = os.path.join(report_dir, "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    return report_dir


def load_report(topic: str, week_current: str, week_previous: str) -> dict | None:
    """
    Loads a previously saved delta report.

    Returns:
        The report dict from JSON, or None if not found.
    """
    topic_slug  = _slugify(topic)
    report_name = f"{week_current}_vs_{week_previous}"
    json_path   = os.path.join(REPORTS_DIR, topic_slug, report_name, "report.json")

    if not os.path.exists(json_path):
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_reports(topic: str) -> list[str]:
    """
    Lists all saved delta reports for a topic, newest first.

    Returns:
        List of report name strings e.g. ["2026-W25_vs_2026-W24", ...]
    """
    topic_slug  = _slugify(topic)
    topic_dir   = os.path.join(REPORTS_DIR, topic_slug)

    if not os.path.exists(topic_dir):
        return []

    reports = sorted(os.listdir(topic_dir), reverse=True)
    return reports