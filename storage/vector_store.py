"""
Job: save chunk dicts into ChromaDB and retrieve them by topic + week.
This is the persistent memory of Driftwatch — everything lives here.

Two operations:
    save(chunks)              → store chunks from the chunker into ChromaDB
    query(topic, week, n)     → retrieve top-n relevant chunks for a topic/week
    query_delta(topic, w1, w2)→ retrieve chunks from two weeks for comparison
"""

import chromadb
from chromadb.config import Settings
import os

# ── Database setup ────────────────────────────────────────────────────────────
# Persistent storage — survives between runs, accumulates over weeks
# All data lives in the /data folder, never committed to git
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")

client = chromadb.PersistentClient(path=DB_PATH)

# One collection holds everything — we filter by metadata (topic, week, source)
# Not separate collections per tracker — one collection scales better
collection = client.get_or_create_collection(
    name="driftwatch",
    metadata={"hnsw:space": "cosine"}  # cosine similarity — better for text than euclidean
)


# ── Save ──────────────────────────────────────────────────────────────────────

def save_chunks(chunks: list[dict]) -> int:
    """
    Saves a list of chunk dicts into ChromaDB.
    Skips chunks that are already stored (idempotent — safe to call twice).

    Returns the number of new chunks actually saved.
    """
    if not chunks:
        return 0

    # ChromaDB expects four separate lists: ids, embeddings, documents, metadatas
    ids         = [c["chunk_id"] for c in chunks]
    embeddings  = [c["embedding"] for c in chunks]
    documents   = [c["text"] for c in chunks]
    metadatas   = [
        {
            "doc_id":  c["doc_id"],
            "title":   c["title"],
            "url":     c["url"],
            "topic":   c["topic"],
            "source":  c["source"],
            "week":    c["week"],   # ← the field that makes delta possible
        }
        for c in chunks
    ]

    # upsert = insert if new, update if exists — never crashes on duplicates
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    return len(chunks)


# ── Query ─────────────────────────────────────────────────────────────────────

def query_chunks(
    query_text: str,
    week: str,
    topic: str = None,
    n_results: int = 10
) -> list[dict]:
    """
    Retrieve the top-n most relevant chunks for a query, filtered by week.

    Args:
        query_text: the search query (will be embedded automatically)
        week:       ISO week string e.g. "2026-W25" — only return chunks from this week
        topic:      optional topic filter for extra precision
        n_results:  how many chunks to return (10 is the default — keeps LLM context small)

    Returns:
        List of result dicts, each containing text + metadata + similarity distance
    """
    # Build the metadata filter
    # ChromaDB uses a MongoDB-style filter syntax
    where = {"week": {"$eq": week}}
    if topic:
        where = {
            "$and": [
                {"week":  {"$eq": week}},
                {"topic": {"$eq": topic}}
            ]
        }

    results = collection.query(
        query_texts=[query_text],   # ChromaDB embeds this automatically
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    # Flatten ChromaDB's nested response into a clean list
    output = []
    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(docs, metas, distances):
        output.append({
            "text":     doc,
            "title":    meta.get("title", ""),
            "url":      meta.get("url", ""),
            "source":   meta.get("source", ""),
            "week":     meta.get("week", ""),
            "topic":    meta.get("topic", ""),
            "score":    round(1 - dist, 4),  # convert distance to similarity (0-1, higher = more relevant)
        })

    return output


def query_delta(
    query_text: str,
    week_current: str,
    week_previous: str,
    n_results: int = 10
) -> tuple[list[dict], list[dict]]:
    """
    Retrieve chunks from TWO weeks simultaneously for delta comparison.
    This is the core of Week 3 — returns (this_week_chunks, last_week_chunks).

    Args:
        query_text:    the topic to compare across weeks
        week_current:  e.g. "2026-W25"
        week_previous: e.g. "2026-W24"
        n_results:     chunks per week

    Returns:
        Tuple of (current_week_chunks, previous_week_chunks)
    """
    current  = query_chunks(query_text, week=week_current,  n_results=n_results)
    previous = query_chunks(query_text, week=week_previous, n_results=n_results)
    return current, previous


# ── Utilities ─────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """
    Returns basic stats about what's stored in ChromaDB.
    Useful for debugging and dashboard display.
    """
    total = collection.count()
    return {
        "total_chunks": total,
        "db_path": DB_PATH,
    }


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from ingestion.arxiv_fetcher import fetch_papers
    from processing.chunker_embedder import process_documents

    # Step 1 — fetch
    print("Fetching papers...")
    papers = fetch_papers(
        topic='cat:cs.LG AND abs:"large language model"',
        max_results=5,
        weeks_ago=0
    )
    print(f"Got {len(papers)} papers")

    # Step 2 — chunk + embed
    print("Chunking and embedding...")
    chunks = process_documents(papers)
    print(f"Got {len(chunks)} chunks")

    # Step 3 — save to ChromaDB
    print("Saving to ChromaDB...")
    saved = save_chunks(chunks)
    print(f"Saved {saved} chunks")

    # Step 4 — verify with a query
    print("\nQuerying: 'what are the latest LLM evaluation methods?'")
    from ingestion.arxiv_fetcher import get_iso_week
    current_week = get_iso_week(0)

    results = query_chunks(
        query_text="latest LLM evaluation methods",
        week=current_week,
        n_results=3
    )

    print(f"\nTop 3 results for week {current_week}:\n")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] score={r['score']} | {r['title']}")
        print(f"       {r['text'][:120]}...")
        print()

    # Step 5 — show DB stats
    stats = get_stats()
    print(f"ChromaDB stats: {stats}")