"""
delta/comparator.py
-------------------
Job: fetch chunks from two weeks out of ChromaDB and structure them
for the delta prompt. Figures out what's in W_current but not W_previous,
what appears in both, and what was in W_previous but dropped off.

This is the core of what makes Driftwatch different from a summarizer.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from storage.vector_store import query_chunks
from ingestion.arxiv_fetcher import get_iso_week


def get_week_pair(weeks_ago_current: int = 0) -> tuple[str, str]:
    """
    Returns (current_week, previous_week) as ISO strings.
    Default: current = this week, previous = one week before current.

    Args:
        weeks_ago_current: which week to treat as "current"
                           0 = this week vs last week
                           1 = last week vs the week before
    """
    current  = get_iso_week(weeks_ago_current)
    previous = get_iso_week(weeks_ago_current + 1)
    return current, previous


def fetch_both_weeks(
    topic: str,
    week_current: str,
    week_previous: str,
    n_results: int = 10
) -> tuple[list[dict], list[dict]]:
    """
    Retrieves chunks from both weeks from ChromaDB.

    Returns:
        (current_chunks, previous_chunks)
        Each is a list of chunk dicts with text, title, url, score, week.
    """
    current_chunks  = query_chunks(
        query_text=topic,
        week=week_current,
        n_results=n_results
    )
    previous_chunks = query_chunks(
        query_text=topic,
        week=week_previous,
        n_results=n_results
    )
    return current_chunks, previous_chunks


def extract_titles(chunks: list[dict]) -> set[str]:
    """Returns the set of unique paper titles from a list of chunks."""
    return {c["title"] for c in chunks if c.get("title")}


def compare_weeks(
    current_chunks: list[dict],
    previous_chunks: list[dict]
) -> dict:
    """
    Compares two sets of chunks and categorizes papers into:
        - new:        in current week, not in previous week
        - continuing: in both weeks
        - dropped:    in previous week, not in current week

    Returns a structured dict used by the delta prompt builder.
    """
    current_titles  = extract_titles(current_chunks)
    previous_titles = extract_titles(previous_chunks)

    new_titles        = current_titles  - previous_titles
    dropped_titles    = previous_titles - current_titles
    continuing_titles = current_titles  & previous_titles

    # Filter chunks into their categories
    new_chunks        = [c for c in current_chunks  if c.get("title") in new_titles]
    continuing_chunks = [c for c in current_chunks  if c.get("title") in continuing_titles]
    dropped_chunks    = [c for c in previous_chunks if c.get("title") in dropped_titles]

    return {
        "new":        new_chunks,        # appeared this week
        "continuing": continuing_chunks, # present in both weeks
        "dropped":    dropped_chunks,    # was there, now gone
        "all_current":  current_chunks,
        "all_previous": previous_chunks,
    }


def prepare_delta_context(
    topic: str,
    week_current: str  = None,
    week_previous: str = None,
    n_results: int = 10
) -> dict:
    """
    Main function. Fetches both weeks and returns everything the
    delta prompt builder needs in one structured object.

    Args:
        topic:         plain English topic e.g. "large language models"
        week_current:  ISO week string e.g. "2026-W25" (defaults to this week)
        week_previous: ISO week string e.g. "2026-W24" (defaults to last week)
        n_results:     chunks per week to retrieve

    Returns:
        {
            "topic":         str,
            "week_current":  str,
            "week_previous": str,
            "new":           list[dict],   ← new this week
            "continuing":    list[dict],   ← in both weeks
            "dropped":       list[dict],   ← dropped off
            "all_current":   list[dict],   ← all current week chunks
            "all_previous":  list[dict],   ← all previous week chunks
            "has_data":      bool          ← False if either week is empty
        }
    """
    # Default to this week vs last week
    if not week_current or not week_previous:
        week_current, week_previous = get_week_pair(0)

    current_chunks, previous_chunks = fetch_both_weeks(
        topic=topic,
        week_current=week_current,
        week_previous=week_previous,
        n_results=n_results
    )

    # Can't do a delta if either week has no data
    has_data = len(current_chunks) > 0 and len(previous_chunks) > 0

    if not has_data:
        return {
            "topic":         topic,
            "week_current":  week_current,
            "week_previous": week_previous,
            "new":           [],
            "continuing":    [],
            "dropped":       [],
            "all_current":   current_chunks,
            "all_previous":  previous_chunks,
            "has_data":      False
        }

    comparison = compare_weeks(current_chunks, previous_chunks)

    return {
        "topic":         topic,
        "week_current":  week_current,
        "week_previous": week_previous,
        "has_data":      True,
        **comparison
    }