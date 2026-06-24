"""
scheduler/daemon.py — Driftwatch background daemon

Runs continuously. Checks every hour whether any tracker is due
based on its frequency setting, and runs the pipeline if so.

To start:
    python scheduler/daemon.py
"""

import json
import logging
import re
import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.arxiv_fetcher import fetch_papers, get_iso_week
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report
from delta.comparator import prepare_delta_context
from delta.delta_prompt import build_delta_messages
from delta.report import save_report


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daemon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Use absolute path so daemon works regardless of where it's launched from
TRACKERS_DIR = Path(__file__).parent.parent / "data" / "trackers"
REPORTS_DIR  = Path(__file__).parent.parent / "data" / "reports"

FREQUENCY_DAYS = {
    "daily":    1,
    "weekly":   7,
    "biweekly": 14,
    "monthly":  30,
}


def should_run(tracker: dict) -> bool:
    last_run  = tracker.get("last_run")
    frequency = tracker.get("frequency", "weekly")

    if not last_run:
        return True

    days_required = FREQUENCY_DAYS.get(frequency, 7)
    last_run_date = datetime.datetime.fromisoformat(last_run)
    days_since    = (datetime.datetime.now() - last_run_date).days
    return days_since >= days_required


def load_all_trackers() -> list[dict]:
    trackers = []
    if not TRACKERS_DIR.exists():
        return trackers
    for path in TRACKERS_DIR.glob("*.json"):
        try:
            with open(path) as f:
                trackers.append(json.load(f))
        except Exception as e:
            log.warning(f"Could not load {path.name}: {e}")
    return trackers


def update_tracker(tracker_id: str, status: str, last_run: str = None):
    path = TRACKERS_DIR / f"{tracker_id}.json"
    if not path.exists():
        return
    with open(path) as f:
        config = json.load(f)
    config["status"] = status
    if last_run:
        config["last_run"] = last_run
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', '_', text)


def _build_arxiv_query(topic: str) -> str:
    return f'cat:cs.LG AND abs:"{topic.strip().lower()}"'


def run_pipeline(tracker: dict):
    tracker_id  = tracker["id"]
    topic       = tracker["topic"]
    report_mode = tracker.get("report_mode", "both")

    log.info(f"Starting pipeline for: '{topic}'")
    update_tracker(tracker_id, "running")

    try:
        # Step 1 — Fetch everything ArXiv returns, no artificial limit
        query      = _build_arxiv_query(topic)
        week_label = get_iso_week(0)
        papers     = fetch_papers(topic=query, weeks_ago=0)

        if not papers:
            log.warning(f"No papers found for '{topic}' this period.")
            update_tracker(tracker_id, "idle", datetime.datetime.now().isoformat())
            return

        log.info(f"Fetched {len(papers)} papers.")

        # Step 2 — Chunk + embed
        chunks = process_documents(papers)
        log.info(f"Created {len(chunks)} chunks.")

        # Step 3 — Save to ChromaDB
        save_chunks(chunks)
        log.info("Saved to ChromaDB.")

        # Step 4 — Summary report
        if report_mode in ("summary", "both"):
            retrieved = query_chunks(query_text=topic, week=week_label)
            if retrieved:
                messages = build_messages(topic, week_label, retrieved)
                summary  = generate_report(messages)

                # Fix: summary has no previous period so save separately,
                # not via save_report which expects two periods
                summary_path = REPORTS_DIR / _slugify(topic) / f"{week_label}_summary"
                summary_path.mkdir(parents=True, exist_ok=True)
                with open(summary_path / "report.txt", "w", encoding="utf-8") as f:
                    f.write(summary)

                log.info("Summary report saved.")

        # Step 5 — Delta report
        if report_mode in ("delta", "both"):
            delta_context = prepare_delta_context(
                topic=topic,
                week_current=week_label,
                week_previous=get_iso_week(1),
            )
            if delta_context.get("has_data"):
                messages     = build_delta_messages(delta_context)
                delta_report = generate_report(messages)
                save_report(
                    topic=topic,
                    week_current=delta_context["week_current"],
                    week_previous=delta_context["week_previous"],
                    report_text=delta_report,
                    context=delta_context
                )
                log.info("Delta report saved.")
            else:
                log.info("Not enough period data for delta yet — skipping.")

    except Exception as e:
        log.error(f"Pipeline failed for '{topic}': {e}")
        update_tracker(tracker_id, "error", datetime.datetime.now().isoformat())
        return

    update_tracker(tracker_id, "idle", datetime.datetime.now().isoformat())
    log.info(f"Pipeline complete for: '{topic}'")


def check_and_run():
    log.info("Checking trackers...")
    trackers = load_all_trackers()

    if not trackers:
        log.info("No trackers found.")
        return

    due = [t for t in trackers if should_run(t)]
    log.info(f"{len(trackers)} tracker(s) total — {len(due)} due.")

    for tracker in due:
        run_pipeline(tracker)


def main():
    log.info("Driftwatch daemon starting...")

    scheduler = BlockingScheduler()
    scheduler.add_job(check_and_run, trigger="interval", hours=1, id="check_trackers")

    log.info("Running initial check...")
    check_and_run()

    log.info("Scheduler active. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Daemon stopped.")


if __name__ == "__main__":
    main()