"""
main.py — Driftwatch entry point
Run this file to execute the full pipeline interactively.

Flow:
    You type a topic → auto-formatted into ArXiv query
    → papers fetched → chunked + embedded → saved to ChromaDB
    → queried back → results printed
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ingestion.arxiv_fetcher import fetch_papers, get_iso_week
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks, get_stats


# ── Query formatter ───────────────────────────────────────────────────────────

def build_arxiv_query(plain_topic: str) -> str:
    """
    Converts plain English topic into a precise ArXiv query.
    'fraud detection'        → cat:cs.LG AND abs:"fraud detection"
    'large language models'  → cat:cs.LG AND abs:"large language models"
    """
    topic = plain_topic.strip().lower()
    return f'cat:cs.LG AND abs:"{topic}"'


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(plain_topic: str, weeks_ago: int = 0, max_results: int = 20):
    """
    Full pipeline: fetch → chunk → embed → save → query.
    Called with plain English topic — no ArXiv syntax needed.
    """
    query = build_arxiv_query(plain_topic)
    week  = get_iso_week(weeks_ago)

    print(f"\n{'─'*55}")
    print(f"  Topic   : {plain_topic}")
    print(f"  Query   : {query}")
    print(f"  Week    : {week}")
    print(f"{'─'*55}\n")

    # Step 1 — Fetch
    print("[ 1/4 ] Fetching papers from ArXiv...")
    papers = fetch_papers(topic=query, max_results=max_results, weeks_ago=weeks_ago)

    if not papers:
        print(f"  No papers found for '{plain_topic}' in week {week}.")
        print("  Try a broader topic or a different week (weeks_ago=1, 2, ...).\n")
        return

    print(f"  Found {len(papers)} papers.\n")

    # Step 2 — Chunk + Embed
    print("[ 2/4 ] Chunking and embedding...")
    chunks = process_documents(papers)
    print(f"  Created {len(chunks)} chunks.\n")

    # Step 3 — Save to ChromaDB
    print("[ 3/4 ] Saving to ChromaDB...")
    saved = save_chunks(chunks)
    stats = get_stats()
    print(f"  Saved {saved} chunks. Total in DB: {stats['total_chunks']}.\n")

    # Step 4 — Query back to verify
    print("[ 4/4 ] Querying most relevant chunks...")
    results = query_chunks(
        query_text=plain_topic,
        week=week,
        n_results=3
    )

    if not results:
        print("  No results returned from query.\n")
        return

    print(f"\n  Top results for '{plain_topic}' — {week}:\n")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] score={r['score']} | {r['title']}")
        print(f"       {r['text'][:150]}...")
        print(f"       → {r['url']}\n")


# ── Interactive prompt ────────────────────────────────────────────────────────

def main():
    print("\n" + "═"*55)
    print("  DRIFTWATCH — Knowledge Radar")
    print("═"*55)
    print("  Type a topic to fetch, embed, and store papers.")
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