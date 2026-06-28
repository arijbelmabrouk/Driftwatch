"""
ingestion/github_fetcher.py
---------------------------
Job: fetch relevant GitHub repos for a given topic and period.
Returns document dicts in the same format as arxiv_fetcher.py
so they flow into chunker_embedder.py and ChromaDB unchanged.

API used: GitHub Search API (free, 5000 req/hour with token)
"""

import os
import base64
import datetime
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

BASE_URL = "https://api.github.com"

# README truncation — captures description and key features
# without pulling in installation guides, changelogs, license text
README_MAX_CHARS = 1500


# ── Query builder ─────────────────────────────────────────────────────────────

def _build_github_query(topic: str, since_date: str) -> str:
    """
    Builds a GitHub search query from a plain topic and a since-date.
    Searches repo name, description, and README content.
    """
    return f"{topic} in:name,description stars:>100 pushed:>{since_date}"


# ── Period helpers ─────────────────────────────────────────────────────────────
# These mirror the logic in arxiv_fetcher.py so period labels are consistent
# across both sources and filter correctly in ChromaDB.

def _get_period_start(frequency: str) -> str:
    """Returns the start date of the current period as an ISO date string."""
    today = datetime.date.today()

    if frequency == "daily":
        return today.isoformat()

    if frequency in ("weekly", "biweekly"):
        # Monday of this week
        start = today - datetime.timedelta(days=today.weekday())
        return start.isoformat()

    if frequency == "monthly":
        return today.replace(day=1).isoformat()

    raise ValueError(f"Unsupported frequency: {frequency}")


def _get_period_label(frequency: str) -> str:
    """
    Returns the period label for the current period.
    Mirrors arxiv_fetcher.get_period_label exactly so both sources
    stamp chunks with the same week identifier in ChromaDB.
    """
    today = datetime.date.today()

    if frequency == "daily":
        return today.isoformat()

    if frequency in ("weekly", "biweekly"):
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "monthly":
        return today.strftime("%Y-%m")

    raise ValueError(f"Unsupported frequency: {frequency}")


# ── README fetcher ────────────────────────────────────────────────────────────

def _fetch_readme(owner: str, repo: str) -> str:
    """
    Fetches and decodes the README for a repo.
    Returns the first README_MAX_CHARS characters, or empty string on failure.
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/readme"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return ""
        data = res.json()
        content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return content[:README_MAX_CHARS]
    except Exception:
        return ""


# ── Main fetcher ──────────────────────────────────────────────────────────────

def fetch_github_repos(
    topic: str,
    frequency: str,
) -> list[dict]:
    """
    Fetch GitHub repos relevant to a topic for the current period.

    Args:
        topic:     plain English topic e.g. "large language models"
        frequency: daily / weekly / biweekly / monthly — no default,
                   always passed explicitly from the tracker config

    Returns:
        List of document dicts ready for chunker_embedder.process_documents().
        Each dict has: source, doc_id, title, text, url, published,
                       authors, topic, week, stars, language
    """
    if not GITHUB_TOKEN:
        print("[github_fetcher] Warning: no GITHUB_TOKEN found. Rate limited to 60 req/hour.")

    since_date   = _get_period_start(frequency)
    period_label = _get_period_label(frequency)
    query        = _build_github_query(topic, since_date)

    url = f"{BASE_URL}/search/repositories"
    params = {
        "q":        query,
        "sort":     "stars",
        "order":    "desc",
        "per_page": 30,    # GitHub Search API maximum per page
    }

    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        res.raise_for_status()
        items = res.json().get("items", [])
    except Exception as e:
        print(f"[github_fetcher] Search failed: {e}")
        return []

    documents = []

    for item in items:
        owner     = item["owner"]["login"]
        repo_name = item["name"]
        full_name = item["full_name"]          # "owner/repo"
        desc      = item.get("description") or ""
        stars     = item.get("stargazers_count", 0)
        language  = item.get("language") or "unknown"
        pushed_at = item.get("pushed_at", "")[:10]  # "2026-06-26"
        html_url  = item["html_url"]

        # Fetch README for richer content — description alone is too short
        readme = _fetch_readme(owner, repo_name)

        # Combine description + README as the document text
        text = f"{desc}\n\n{readme}".strip()
        if not text:
            continue  # skip repos with no content at all

        doc = {
            "source":    "github",
            "doc_id":    full_name,
            "title":     f"{full_name} — {desc[:80]}" if desc else full_name,
            "text":      text,
            "url":       html_url,
            "published": pushed_at,
            "authors":   [owner],
            "topic":     topic,
            "week":      period_label,   # ← same field name as arxiv_fetcher
            "stars":     stars,
            "language":  language,
        }
        documents.append(doc)

    return documents


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    topic     = input("Topic: ").strip() or "large language models"
    frequency = input("Frequency (daily/weekly/biweekly/monthly) [default: weekly]: ").strip() or "weekly"

    print(f"\nFetching GitHub repos for: '{topic}' ({frequency})")
    print(f"Period: {_get_period_label(frequency)}\n")

    repos = fetch_github_repos(topic=topic, frequency=frequency)

    if not repos:
        print("No repos found. Check your GITHUB_TOKEN in .env")
    else:
        for r in repos:
            print(f"[{r['week']}] {r['title']}")
            print(f"  stars    : {r['stars']}")
            print(f"  language : {r['language']}")
            print(f"  url      : {r['url']}")
            print(f"  text     : {r['text'][:120]}...")
            print()

    print(f"Total: {len(repos)} repos fetched.")