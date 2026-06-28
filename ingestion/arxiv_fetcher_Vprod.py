"""
ingestion/arxiv_fetcher.py
--------------------------
Job: fetch papers from ArXiv for a given topic and period.
Returns a clean list of paper dicts ready for chunker_embedder.process_documents().
"""

import arxiv
import datetime


# ── Internal date helpers ─────────────────────────────────────────────────────

def _get_week_range(weeks_ago: int = 0):
    """Returns (start_date, end_date) for a given week. Internal use only."""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday())
    start = start - datetime.timedelta(weeks=weeks_ago)
    end   = start + datetime.timedelta(days=6)
    return start, end


def _get_period_date_range(frequency: str):
    """Returns (start_date, end_date) for the current period."""
    if frequency == "daily":
        today = datetime.date.today()
        return today, today

    if frequency in ("weekly", "biweekly"):
        return _get_week_range()

    if frequency == "monthly":
        today      = datetime.date.today()
        start      = today.replace(day=1)
        next_month = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        end        = next_month - datetime.timedelta(days=1)
        return start, end

    raise ValueError(f"Unsupported frequency: {frequency}")


# ── Public period label functions ─────────────────────────────────────────────
# Imported by api/main.py and scheduler/daemon.py

def get_period_label(frequency: str) -> str:
    """Returns the current period label for a tracker frequency."""
    today = datetime.date.today()

    if frequency == "daily":
        return today.isoformat()

    if frequency in ("weekly", "biweekly"):
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "monthly":
        return today.strftime("%Y-%m")

    raise ValueError(f"Unsupported frequency: {frequency}")


def get_previous_period_label(frequency: str) -> str:
    """Returns the previous period label for a tracker frequency."""
    today = datetime.date.today()

    if frequency == "daily":
        return (today - datetime.timedelta(days=1)).isoformat()

    if frequency == "weekly":
        prev = today - datetime.timedelta(weeks=1)
        year, week, _ = prev.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "biweekly":
        prev = today - datetime.timedelta(weeks=2)
        year, week, _ = prev.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "monthly":
        first_of_month = today.replace(day=1)
        prev           = first_of_month - datetime.timedelta(days=1)
        return prev.strftime("%Y-%m")

    raise ValueError(f"Unsupported frequency: {frequency}")


# ── Main fetcher ──────────────────────────────────────────────────────────────

def fetch_papers(topic: str, frequency: str) -> list[dict]:
    """
    Fetch papers from ArXiv for a given topic and current period.

    Args:
        topic:     ArXiv query string e.g. 'cat:cs.LG AND abs:"fraud detection"'
        frequency: daily / weekly / biweekly / monthly —
                   always passed explicitly from the tracker config

    Returns:
        List of paper dicts with: source, paper_id, title, abstract,
        url, published, authors, topic, week
    """
    start_date, end_date = _get_period_date_range(frequency)
    period_label         = get_period_label(frequency)

    search = arxiv.Search(
        query=topic,
        max_results=500,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    client = arxiv.Client()
    papers = []

    for result in client.results(search):
        pub_date = result.updated.date()

        if pub_date < start_date or pub_date > end_date:
            continue

        papers.append({
            "source":    "arxiv",
            "paper_id":  result.get_short_id(),
            "title":     result.title,
            "abstract":  result.summary,
            "url":       result.entry_id,
            "published": str(pub_date),
            "authors":   [a.name for a in result.authors[:5]],
            "topic":     topic,
            "week":      period_label,
        })

    return papers