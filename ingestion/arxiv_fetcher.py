"""
Job: fetch papers from ArXiv for a given topic and date range.
Returns a clean list of paper dicts.
"""

import arxiv
import datetime
from typing import Optional



def get_week_range(weeks_ago: int = 0):
    """
    Returns (start_date, end_date) for a given week.
    weeks_ago=0 → this week
    weeks_ago=1 → last week
    """
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday())  # this Monday
    start = start - datetime.timedelta(weeks=weeks_ago)        # go back N weeks
    end = start + datetime.timedelta(days=6)
    return start, end


def get_iso_week(weeks_ago: int = 0) -> str:
    """
    Returns ISO week string like '2026-W24'.
    This is the metadata stamp used for delta comparisons later.
    """
    start, _ = get_week_range(weeks_ago)
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


def fetch_papers(
    topic: str,
    max_results: int = 500,
    weeks_ago: int = 0
) -> list[dict]:
    """
    Fetch papers from ArXiv for a given topic.

    Args:
        topic:       plain language search query, e.g. "fraud detection deep learning"
        max_results: how many papers to fetch (50 is a good default for weekly runs)
        weeks_ago:   0 = this week, 1 = last week, etc.

    Returns:
        List of paper dicts, each containing:
        {
            "paper_id":    "2401.12345",
            "title":       "...",
            "abstract":    "...",
            "url":         "https://arxiv.org/abs/2401.12345",
            "published":   "2026-06-09",
            "authors":     ["Author One", "Author Two"],
            "topic":       "fraud detection deep learning",
            "week":        "2026-W24"
        }
    """
    start_date, end_date = get_week_range(weeks_ago)
    week_label = get_iso_week(weeks_ago)

    # Build the ArXiv search
    search = arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    client = arxiv.Client()
    papers = []

    for result in client.results(search):
        pub_date = result.updated.date()

        # If we've gone past the target week, stop — results are sorted newest first
        if pub_date < start_date:
            continue

        if pub_date > end_date:
            continue

        paper = {
            "source": "arxiv",
            "paper_id":  result.get_short_id(),
            "title":     result.title,
            "abstract":  result.summary,
            "url":       result.entry_id,
            "published": str(pub_date),
            "authors":   [a.name for a in result.authors[:5]],
            "topic":     topic,
            "week":      week_label
        }
        papers.append(paper)

    return papers


# ── Quick test ──────────────────────────────────────────────────────────────
# Run this file directly to verify it works:
#   python ingestion/arxiv_fetcher.py

if __name__ == "__main__":
    print("Fetching papers for: Machine Learning")
    print("Week:", get_iso_week(0))
    print()

    papers = fetch_papers(
        topic='cat:cs.LG AND abs:"large language model"',
        max_results=20,
        weeks_ago=0
    )

    if not papers:
        print("No papers found.")
    else:
        for p in papers:
            print(f"[{p['week']}] {p['title']}")
            print(f"  → {p['url']}")
            print(f"  Authors: {', '.join(p['authors'])}")
            print()

    print(f"Total: {len(papers)} papers fetched.")