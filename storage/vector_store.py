"""
Job: save chunk dicts into ChromaDB and retrieve them by topic + week.
This is the persistent memory of Driftwatch — everything lives here.
"""

import chromadb
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")

client = chromadb.PersistentClient(path=DB_PATH)

collection = client.get_or_create_collection(
    name="driftwatch",
    metadata={"hnsw:space": "cosine"}
)


# ── Save ──────────────────────────────────────────────────────────────────────

def save_chunks(chunks: list[dict]) -> int:
    if not chunks:
        return 0

    ids        = [c["chunk_id"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    documents  = [c["text"] for c in chunks]
    metadatas  = [
        {
            "doc_id": c["doc_id"],
            "title":  c["title"],
            "url":    c["url"],
            "topic":  c["topic"],
            "source": c["source"],
            "week":   c["week"],
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    return len(chunks)


# ── Query ─────────────────────────────────────────────────────────────────────

def _smart_n_results() -> int:
    """
    Calculate how many chunks to retrieve based on token budget.

    Groq llama-3.1-8b-instant: 131k context window.
    Reserve 2,000 tokens for system prompt + instructions + response.
    Each chunk ≈ 500 characters ≈ 125 tokens.
    Max chunks = (131,000 - 2,000) / 125 ≈ 1,032.

    Cap at 50 for report focus — more chunks dilute the signal.
    ChromaDB returns fewer if not enough exist for that week.
    """
    try:
        total = collection.count()
        return min(50, total) if total > 0 else 10
    except Exception:
        return 10


def query_chunks(
    query_text: str,
    week: str,
    topic: str = None,
    n_results: int = None       # None = calculate automatically from token budget
) -> list[dict]:
    """
    Retrieve the most relevant chunks for a query, filtered by week.
    """
    if n_results is None:
        n_results = _smart_n_results()

    where = {"week": {"$eq": week}}
    if topic:
        where = {
            "$and": [
                {"week":  {"$eq": week}},
                {"topic": {"$eq": topic}}
            ]
        }

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    output = []
    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(docs, metas, distances):
        output.append({
            "text":   doc,
            "title":  meta.get("title", ""),
            "url":    meta.get("url", ""),
            "source": meta.get("source", ""),
            "week":   meta.get("week", ""),
            "topic":  meta.get("topic", ""),
            "score":  round(1 - dist, 4),
        })

    return output


def query_delta(
    query_text: str,
    week_current: str,
    week_previous: str,
    n_results: int = None
) -> tuple[list[dict], list[dict]]:
    current  = query_chunks(query_text, week=week_current,  n_results=n_results)
    previous = query_chunks(query_text, week=week_previous, n_results=n_results)
    return current, previous


# ── Utilities ─────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    total = collection.count()
    return {
        "total_chunks": total,
        "db_path": DB_PATH,
    }