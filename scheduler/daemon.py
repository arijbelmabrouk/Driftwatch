"""
scheduler/daemon.py — Driftwatch background daemon

Runs continuously. Checks every hour whether any tracker is due
based on its frequency setting, and runs the pipeline if so.

To start:
    python scheduler/daemon.py
"""

import logging
import re
import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from ingestion.github_fetcher import fetch_github_repos
from ingestion.hn_fetcher import fetch_hn_stories
import database

from ingestion.arxiv_fetcher import (
    fetch_papers,
    get_period_label,
    get_previous_period_label,
)
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report
from delta.comparator import prepare_delta_context
from delta.delta_prompt import build_delta_messages
import time
from delta.report import save_report, save_summary
from notifications.emailer import send_report_email


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daemon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "data" / "reports"

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


def load_all_trackers_for_user(user_id: str) -> list[dict]:
    return database.list_trackers(user_id)


def update_tracker(tracker: dict, status: str, last_run: str = None):
    tracker["status"] = status
    if last_run:
        tracker["last_run"] = last_run
    database.save_tracker(tracker)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', '_', text)


def _build_arxiv_query(topic: str) -> str:
    return f'cat:cs.LG AND abs:"{topic.strip().lower()}"'


def run_pipeline(tracker: dict, user: dict | None = None):
    tracker_id  = tracker["id"]
    topic       = tracker["topic"]
    report_mode = tracker.get("report_mode", "both")

    if user is None:
        user = database.get_user_by_id(tracker.get("user_id")) or {}

    log.info(f"Starting pipeline for: '{topic}'")
    update_tracker(tracker, "running")

    generated_reports    = []
    summary_text_for_email = ""
    delta_text_for_email   = ""

    try:
        # Step 1 — Fetch from ArXiv
        query      = _build_arxiv_query(topic)
        week_label = get_period_label(tracker.get("frequency", "weekly"))
        papers     = fetch_papers(topic=query, frequency=tracker.get("frequency", "weekly"))
        log.info(f"Fetched {len(papers)} ArXiv papers.")

        # Step 1b — Fetch from GitHub
        github_docs = fetch_github_repos(
            topic=topic,
            frequency=tracker.get("frequency", "weekly"),
        )
        log.info(f"Fetched {len(github_docs)} GitHub repos.")

        # Step 1c — Fetch from HackerNews
        hn_docs = fetch_hn_stories(
            topic=topic,
            frequency=tracker.get("frequency", "weekly"),
        )
        log.info(f"Fetched {len(hn_docs)} HackerNews stories.")

        # Merge all sources
        all_documents = papers + github_docs + hn_docs

        if not all_documents:
            log.warning(f"No data found for '{topic}' this period.")
            update_tracker(tracker, "idle", datetime.datetime.now().isoformat())
            return

        # Step 2 — Chunk + embed
        chunks = process_documents(all_documents)
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

                report_dir = save_summary(
                    topic=topic,
                    week_current=week_label,
                    report_text=summary,
                    chunks=retrieved
                )
                generated_reports.append(report_dir)
                summary_text_for_email = summary
                log.info("Summary report saved.")
                time.sleep(3)  # avoid Groq 429 back-to-back

        # Step 5 — Delta report
        if report_mode in ("delta", "both"):
            delta_context = prepare_delta_context(
                topic=topic,
                week_current=week_label,
                week_previous=get_previous_period_label(tracker.get("frequency", "weekly")),
            )
            if delta_context.get("has_data"):
                messages     = build_delta_messages(delta_context)
                delta_report = generate_report(messages)

                report_dir = save_report(
                    topic=topic,
                    week_current=delta_context["week_current"],
                    week_previous=delta_context["week_previous"],
                    report_text=delta_report,
                    context=delta_context
                )
                generated_reports.append(report_dir)
                delta_text_for_email = delta_report
                log.info("Delta report saved.")
            else:
                log.info("Not enough period data for delta yet — skipping.")

    except Exception as e:
        log.error(f"Pipeline failed for '{topic}': {e}")
        update_tracker(tracker, "error", datetime.datetime.now().isoformat())
        return

    update_tracker(tracker, "idle", datetime.datetime.now().isoformat())
    log.info(f"Pipeline complete for: '{topic}'")

    # ── Send email with full report content ───────────────────────────────────
    if generated_reports and user.get("email"):
        try:
            email_parts = []

            if summary_text_for_email:
                email_parts.append(
                    f"SUMMARY REPORT\n{'=' * 50}\n{summary_text_for_email}"
                )

            if delta_text_for_email:
                email_parts.append(
                    f"DELTA REPORT\n{'=' * 50}\n{delta_text_for_email}"
                )

            full_report_text = "\n\n".join(email_parts) if email_parts else "Report generated — open the dashboard to view."

            send_report_email(
                recipient=user["email"],
                topic=topic,
                report_paths=generated_reports,
                report_text=full_report_text,
            )
            log.info(f"Report email sent to {user['email']}.")
        except Exception as exc:
            log.warning(f"Could not send report email for '{topic}': {exc}")


def check_and_run():
    log.info("Checking trackers...")
    database.init_db()

    users = []
    try:
        with database.connect() as conn:
            rows = conn.execute("SELECT id, email FROM users").fetchall()
            users = [dict(row) for row in rows]
    except Exception as exc:
        log.warning(f"Could not load users from DB: {exc}")
        return

    if not users:
        log.info("No users found.")
        return

    for user in users:
        user_id  = user["id"]
        trackers = load_all_trackers_for_user(user_id)
        if not trackers:
            continue

        due = [t for t in trackers if should_run(t)]
        log.info(f"User {user.get('email', user_id)}: {len(trackers)} tracker(s) — {len(due)} due.")

        for tracker in due:
            run_pipeline(tracker, user)


def main():
    log.info("Driftwatch daemon starting...")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        check_and_run,
        trigger="interval",
        hours=1,
        id="check_trackers"
    )

    log.info("Running initial check...")
    check_and_run()

    log.info("Scheduler active. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Daemon stopped.")


if __name__ == "__main__":
    main()