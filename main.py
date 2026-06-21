"""
main.py — Driftwatch entry point

Two modes:
    [1] Weekly summary  — summarize what papers say about a topic this week
    [2] Delta report    — compare this week vs last week, what shifted?
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ingestion.arxiv_fetcher import fetch_papers, get_iso_week
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks, get_stats
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report
from delta.comparator import prepare_delta_context
from delta.delta_prompt import build_delta_messages
from delta.report import save_report, load_report


# ── Query formatter ───────────────────────────────────────────────────────────

def build_arxiv_query(plain_topic: str) -> str:
    topic = plain_topic.strip().lower()
    return f'cat:cs.LG AND abs:"{topic}"'


# ── Ingestion (shared by both modes) ─────────────────────────────────────────

def ingest(plain_topic: str, weeks_ago: int = 0, max_results: int = 20):
    """Fetch → chunk → embed → save. Returns week label."""
    query = build_arxiv_query(plain_topic)
    week  = get_iso_week(weeks_ago)

    print(f"\n[ 1/3 ] Fetching papers from ArXiv...")
    papers = fetch_papers(topic=query, max_results=max_results, weeks_ago=weeks_ago)

    if not papers:
        print(f"  No papers found for '{plain_topic}' in week {week}.")
        return None

    print(f"  Found {len(papers)} papers.")

    print(f"[ 2/3 ] Chunking and embedding...")
    chunks = process_documents(papers)
    print(f"  Created {len(chunks)} chunks.")

    print(f"[ 3/3 ] Saving to ChromaDB...")
    saved = save_chunks(chunks)
    stats = get_stats()
    print(f"  Saved {saved} chunks. Total in DB: {stats['total_chunks']}.\n")

    return week


# ── Mode 1: Weekly Summary ────────────────────────────────────────────────────

def run_summary(plain_topic: str, weeks_ago: int = 0, max_results: int = 20):
    query = build_arxiv_query(plain_topic)
    week  = get_iso_week(weeks_ago)

    print(f"\n{'─'*55}")
    print(f"  Mode    : Weekly Summary")
    print(f"  Topic   : {plain_topic}")
    print(f"  Week    : {week}")
    print(f"{'─'*55}")

    week = ingest(plain_topic, weeks_ago, max_results)
    if not week:
        return

    print("[ 4/5 ] Retrieving most relevant chunks...")
    results = query_chunks(query_text=plain_topic, week=week, n_results=10)
    if not results:
        print("  No results from ChromaDB.\n")
        return
    print(f"  Retrieved {len(results)} chunks.\n")

    print("[ 5/5 ] Generating summary with Groq...")
    messages = build_messages(topic=plain_topic, week=week, chunks=results)
    report   = generate_report(messages)

    print(f"\n{'═'*55}")
    print(f"  WEEKLY REPORT — {plain_topic.upper()}")
    print(f"  {week}")
    print(f"{'═'*55}\n")
    print(report)
    print(f"\n{'═'*55}\n")


# ── Mode 2: Delta Report ──────────────────────────────────────────────────────

def run_delta(plain_topic: str, max_results: int = 20):
    week_current  = get_iso_week(0)
    week_previous = get_iso_week(1)

    print(f"\n{'─'*55}")
    print(f"  Mode    : Delta Report")
    print(f"  Topic   : {plain_topic}")
    print(f"  Comparing: {week_previous} → {week_current}")
    print(f"{'─'*55}")

    # Check if we already have a saved report for this period
    existing = load_report(plain_topic, week_current, week_previous)
    if existing:
        print(f"\n  Found saved report for {week_previous} → {week_current}")
        use_existing = input("  Use saved report? (y/n) [default: y]: ").strip().lower()
        if use_existing != "n":
            print(f"\n{'═'*55}")
            print(f"  DELTA REPORT — {plain_topic.upper()}")
            print(f"  {week_previous} → {week_current}")
            print(f"{'═'*55}\n")
            print(existing["report"])
            print(f"\n{'═'*55}\n")
            return

    # Ingest current week if needed
    print(f"\nIngesting current week ({week_current})...")
    ingest(plain_topic, weeks_ago=0, max_results=max_results)

    # Prepare delta context — fetch both weeks from ChromaDB
    print("Preparing delta context...")
    context = prepare_delta_context(
        topic=plain_topic,
        week_current=week_current,
        week_previous=week_previous,
        n_results=10
    )

    if not context["has_data"]:
        missing = []
        if not context["all_current"]:
            missing.append(week_current)
        if not context["all_previous"]:
            missing.append(week_previous)
        print(f"\n  Cannot generate delta — no data found for: {', '.join(missing)}")
        print(f"  Run a summary first for the missing week(s) to populate ChromaDB.\n")
        return

    print(f"  Current week  : {len(context['all_current'])} chunks")
    print(f"  Previous week : {len(context['all_previous'])} chunks")
    print(f"  New papers    : {len(set(c['title'] for c in context['new']))}")
    print(f"  Continuing    : {len(set(c['title'] for c in context['continuing']))}")
    print(f"  Dropped off   : {len(set(c['title'] for c in context['dropped']))}\n")

    # Generate delta report
    print("Generating delta report with Groq...")
    messages    = build_delta_messages(context)
    report_text = generate_report(messages)

    # Save to disk
    report_dir = save_report(
        topic=plain_topic,
        week_current=week_current,
        week_previous=week_previous,
        report_text=report_text,
        context=context
    )
    print(f"  Report saved to: {report_dir}\n")

    # Print the report
    print(f"\n{'═'*55}")
    print(f"  DELTA REPORT — {plain_topic.upper()}")
    print(f"  {week_previous} → {week_current}")
    print(f"{'═'*55}\n")
    print(report_text)
    print(f"\n{'═'*55}\n")


# ── Interactive prompt ────────────────────────────────────────────────────────

def main():
    print("\n" + "═"*55)
    print("  DRIFTWATCH — Knowledge Radar")
    print("═"*55)
    print("  Type 'quit' to exit.\n")

    while True:
        # Topic
        topic = input("  Topic: ").strip()
        if topic.lower() in ("quit", "exit", "q"):
            print("\n  Exiting Driftwatch.\n")
            break
        if not topic:
            print("  Please enter a topic.\n")
            continue

        # Mode selection
        print("\n  Mode:")
        print("  [1] Weekly summary  (single week)")
        print("  [2] Delta report    (compare this week vs last week)")
        mode = input("  Choose (1 or 2) [default: 1]: ").strip()
        if mode not in ("1", "2", ""):
            print("  Invalid choice, using 1.\n")
            mode = "1"
        if not mode:
            mode = "1"

        # Max results
        max_input = input("  Max papers to fetch [default: 20]: ").strip()
        try:
            max_results = int(max_input) if max_input else 20
        except ValueError:
            max_results = 20

        # Run selected mode
        if mode == "1":
            weeks_input = input("  Weeks ago (0 = this week, 1 = last week) [default: 0]: ").strip()
            try:
                weeks_ago = int(weeks_input) if weeks_input else 0
            except ValueError:
                weeks_ago = 0
            run_summary(plain_topic=topic, weeks_ago=weeks_ago, max_results=max_results)
        else:
            run_delta(plain_topic=topic, max_results=max_results)

        # Continue?
        again = input("  Run another? (y/n) [default: y]: ").strip().lower()
        if again == "n":
            print("\n  Exiting Driftwatch.\n")
            break
        print()


if __name__ == "__main__":
    main()