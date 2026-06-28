"""
ingestion/hn_fetcher.py
-----------------------
Job: fetch relevant HackerNews stories and comments for a given topic and period.
Returns document dicts in the same format as arxiv_fetcher.py and github_fetcher.py
so they flow into chunker_embedder.py and ChromaDB unchanged.

API used: Algolia HN Search API (official, free, no key required)
Docs: https://hn.algolia.com/api
"""

import requests
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Period helpers — imported from arxiv_fetcher to guarantee consistent
# period stamps across all sources in ChromaDB
from ingestion.arxiv_fetcher import (
    get_period_label,
    get_period_date_range,
)

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unix_timestamp(date) -> int:
    """Convert a datetime.date to a Unix timestamp (start of day UTC)."""
    import datetime
    dt = datetime.datetime.combine(date, datetime.time.min)
    return int(dt.timestamp())


def _fetch_comments(story_id: int, max_comments: int = 5) -> list[str]:
    """
    Fetches the top comments for a story via the Algolia items endpoint.
    Returns a list of comment text strings.
    """
    url = f"{ALGOLIA_BASE}/items/{story_id}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return []
        data = res.json()
        children = data.get("children", [])
        comments = []
        for child in children[:max_comments]:
            text = child.get("text") or ""
            if text.strip():
                comments.append(text.strip())
        return comments
    except Exception:
        return []


# ── Main fetcher ──────────────────────────────────────────────────────────────

def fetch_hn_stories(
    topic: str,
    frequency: str,
) -> list[dict]:
    """
    Fetch HackerNews stories mentioning the topic in the current period.

    Uses the Algolia HN Search API — official, free, no key required.
    Fetches stories + top 5 comments per story for richer signal.

    Args:
        topic:     plain English topic e.g. "large language models"
        frequency: daily / weekly / biweekly / monthly — passed from tracker config.
                   Controls the date window and the period label stamped on chunks.

    Returns:
        List of document dicts ready for chunker_embedder.process_documents().
        Each dict has: source, doc_id, title, text, url, published,
                       authors, topic, week, points, num_comments
    """
    # Use arxiv_fetcher's period helpers — single source of truth
    start_date, end_date = get_period_date_range(frequency)
    period_label         = get_period_label(frequency)

    # Convert dates to Unix timestamps for Algolia's numeric filter
    start_ts = _unix_timestamp(start_date)
    end_ts   = _unix_timestamp(end_date)

    # Search stories (not comments) matching the topic in the period
    url = f"{ALGOLIA_BASE}/search"
    params = {
        "query":        topic,
        "tags":         "story",           # only stories, not comments
        "numericFilters": f"created_at_i>{start_ts},created_at_i<{end_ts}",
        "hitsPerPage":  50,                # fetch up to 50 — filter by period server-side
        "attributesToRetrieve": "objectID,title,url,points,num_comments,author,created_at,story_text",
    }

    try:
        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        hits = res.json().get("hits", [])
    except Exception as e:
        print(f"[hn_fetcher] Search failed: {e}")
        return []

    documents = []

    for hit in hits:
        story_id    = hit.get("objectID", "")
        title       = hit.get("title", "")
        story_url   = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        hn_url      = f"https://news.ycombinator.com/item?id={story_id}"
        points      = hit.get("points", 0)
        num_comments = hit.get("num_comments", 0)
        author      = hit.get("author", "unknown")
        story_text  = hit.get("story_text") or ""  # text for Ask HN / self posts
        published   = hit.get("created_at", "")[:10]  # "2026-06-26"

        # Skip stories with no title
        if not title.strip():
            continue

        # Fetch top 5 comments for richer discussion signal
        comments = _fetch_comments(int(story_id)) if story_id else []

        # Build document text: story title + self-text + top comments
        text_parts = [title]
        if story_text.strip():
            text_parts.append(story_text.strip())
        if comments:
            text_parts.append("Top comments:\n" + "\n".join(f"- {c[:300]}" for c in comments))

        text = "\n\n".join(text_parts)

        doc = {
            "source":       "hn",
            "doc_id":       f"hn_{story_id}",
            "title":        title,
            "text":         text,
            "url":          hn_url,           # always link to HN thread, not external URL
            "published":    published,
            "authors":      [author],
            "topic":        topic,
            "week":         period_label,     # same field as arxiv + github chunks
            "points":       points,
            "num_comments": num_comments,
        }
        documents.append(doc)

    return documents


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    topic     = input("Topic: ").strip() or "large language models"
    frequency = input("Frequency (daily/weekly/biweekly/monthly) [default: weekly]: ").strip() or "weekly"

    print(f"\nFetching HN stories for: '{topic}' ({frequency})")
    print(f"Period : {get_period_label(frequency)}")
    print(f"Since  : {get_period_date_range(frequency)[0]}\n")

    stories = fetch_hn_stories(topic=topic, frequency=frequency)

    if not stories:
        print("No stories found for this period.")
    else:
        for s in stories:
            print(f"[{s['week']}] {s['title']}")
            print(f"  points   : {s['points']} | comments: {s['num_comments']}")
            print(f"  url      : {s['url']}")
            print(f"  text     : {s['text'][:150]}...")
            print()

    print(f"Total: {len(stories)} stories fetched.")