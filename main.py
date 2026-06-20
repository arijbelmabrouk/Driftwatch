"""
main.py — Driftwatch entry point
Run this file to execute the full pipeline interactively.

Flow:
    You type a topic → auto-formatted into ArXiv query
    → papers fetched → chunked + embedded → saved to ChromaDB
    → retrieved → LLM generates structured report → printed
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ingestion.arxiv_fetcher import fetch_papers, get_iso_week
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks, get_stats
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report


# ── Query formatter ───────────────────────────────────────────────────────────

def build_arxiv_query(plain_topic: str) -> str:
    """
    Converts plain English topic into a precise ArXiv query.
    'fraud detection'       → cat:cs.LG AND abs:"fraud detection"
    'large language models' → cat:cs.LG AND abs:"large language models"
    """
    topic = plain_topic.strip().lower()
    return f'cat:cs.LG AND abs:"{topic}"'


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(plain_topic: str, weeks_ago: int = 0, max_results: int = 20):
    """
    Full pipeline: fetch → chunk → embed → save → retrieve → generate report.
    """
    query = build_arxiv_query(plain_topic)
    week  = get_iso_week(weeks_ago)

    print(f"\n{'─'*55}")
    print(f"  Topic   : {plain_topic}")
    print(f"  Query   : {query}")
    print(f"  Week    : {week}")
    print(f"{'─'*55}\n")

    # Step 1 — Fetch
    print("[ 1/5 ] Fetching papers from ArXiv...")
    papers = fetch_papers(topic=query, max_results=max_results, weeks_ago=weeks_ago)

    if not papers:
        print(f"  No papers found for '{plain_topic}' in week {week}.")
        print("  Try a broader topic or a different week (weeks_ago=1, 2, ...).\n")
        return

    print(f"  Found {len(papers)} papers.\n")

    # Step 2 — Chunk + Embed
    print("[ 2/5 ] Chunking and embedding...")
    chunks = process_documents(papers)
    print(f"  Created {len(chunks)} chunks.\n")

    # Step 3 — Save to ChromaDB
    print("[ 3/5 ] Saving to ChromaDB...")
    saved = save_chunks(chunks)
    stats = get_stats()
    print(f"  Saved {saved} chunks. Total in DB: {stats['total_chunks']}.\n")

    # Step 4 — Retrieve top chunks for report generation
    print("[ 4/5 ] Retrieving most relevant chunks...")
    results = query_chunks(
        query_text=plain_topic,
        week=week,
        n_results=10
    )

    if not results:
        print("  No results returned from ChromaDB.\n")
        return

    print(f"  Retrieved {len(results)} chunks.\n")

    # Step 5 — Generate report with LLM
    print("[ 5/5 ] Generating report with Groq...")
    messages = build_messages(topic=plain_topic, week=week, chunks=results)
    report   = generate_report(messages)

    # Print the report
    print(f"\n{'═'*55}")
    print(f"  WEEKLY REPORT — {plain_topic.upper()}")
    print(f"  {week}")
    print(f"{'═'*55}\n")
    print(report)
    print(f"\n{'═'*55}\n")


# ── Interactive prompt ────────────────────────────────────────────────────────

def main():
    print("\n" + "═"*55)
    print("  DRIFTWATCH — Knowledge Radar")
    print("═"*55)
    print("  Type a topic to fetch, embed, store, and report.")
    print("  Type 'quit' to exit.\n")

    while True:
        # Topic input
        topic = input("  Topic: ").strip()
        if topic.lower() in ("quit", "exit", "q"):
            print("\n  Exiting Driftwatch.\n")
            break
        if not topic:
            print("  Please enter a topic.\n")
            continue

        # Weeks ago input
        weeks_input = input("  Weeks ago (0 = this week, 1 = last week) [default: 0]: ").strip()
        try:
            weeks_ago = int(weeks_input) if weeks_input else 0
        except ValueError:
            print("  Invalid input, using 0.\n")
            weeks_ago = 0

        # Max results input
        max_input = input("  Max papers to fetch [default: 20]: ").strip()
        try:
            max_results = int(max_input) if max_input else 20
        except ValueError:
            print("  Invalid input, using 20.\n")
            max_results = 20

        # Run the full pipeline
        run_pipeline(plain_topic=topic, weeks_ago=weeks_ago, max_results=max_results)

        # Ask if they want to run again
        again = input("  Run another topic? (y/n) [default: y]: ").strip().lower()
        if again == "n":
            print("\n  Exiting Driftwatch.\n")
            break
        print()


if __name__ == "__main__":
    main()