"""
Job: fetch papers from ArXiv for a given topic and date range.
Returns a clean list of paper dicts.
"""

import arxiv
import datetime


def get_week_range(weeks_ago: int = 0):
    """
    Returns (start_date, end_date) for a given week.
    weeks_ago=0 → this week
    weeks_ago=1 → last week
    """
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday())
    start = start - datetime.timedelta(weeks=weeks_ago)
    end   = start + datetime.timedelta(days=6)
    return start, end


def get_iso_week(weeks_ago: int = 0) -> str:
    """Returns ISO week string like '2026-W24'."""
    start, _ = get_week_range(weeks_ago)
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


def get_period_label(frequency: str) -> str:
    """
    Returns the current period label for a tracker frequency.
    No default — frequency must always be passed explicitly from tracker config.
    """
    frequency = frequency.lower()
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
    """
    Returns the previous period label for a tracker frequency.
    No default — frequency must always be passed explicitly from tracker config.
    """
    frequency = frequency.lower()
    today = datetime.date.today()

    if frequency == "daily":
        return (today - datetime.timedelta(days=1)).isoformat()

    if frequency == "weekly":
        previous = today - datetime.timedelta(weeks=1)
        year, week, _ = previous.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "biweekly":
        previous = today - datetime.timedelta(weeks=2)
        year, week, _ = previous.isocalendar()
        return f"{year}-W{week:02d}"

    if frequency == "monthly":
        first_of_month     = today.replace(day=1)
        previous_month_end = first_of_month - datetime.timedelta(days=1)
        return previous_month_end.strftime("%Y-%m")

    raise ValueError(f"Unsupported frequency: {frequency}")


def get_period_date_range(frequency: str, weeks_ago: int = 0):
    """
    Returns the date range for the current period based on frequency.
    No default — frequency must always be passed explicitly from tracker config.
    """
    frequency = frequency.lower()

    if frequency == "daily":
        today = datetime.date.today()
        return today, today

    if frequency in ("weekly", "biweekly"):
        return get_week_range(weeks_ago)

    if frequency == "monthly":
        today      = datetime.date.today()
        start      = today.replace(day=1)
        next_month = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        end        = next_month - datetime.timedelta(days=1)
        return start, end

    raise ValueError(f"Unsupported frequency: {frequency}")


def fetch_papers(
    topic: str,
    frequency: str,
    max_results: int = 500,
    weeks_ago: int = 0,
) -> list[dict]:
    """
    Fetch papers from ArXiv for a given topic and period.

    Args:
        topic:       ArXiv query string e.g. 'cat:cs.LG AND abs:"fraud detection"'
        frequency:   daily / weekly / biweekly / monthly — no default,
                     always passed explicitly from the tracker config
        max_results: ArXiv API page size (500 is safe upper bound)
        weeks_ago:   0 = current period, 1 = previous period (for backfill)
    """
    start_date, end_date = get_period_date_range(frequency, weeks_ago)
    period_label         = get_period_label(frequency)

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

        if pub_date < start_date or pub_date > end_date:
            continue

        paper = {
            "source":    "arxiv",
            "paper_id":  result.get_short_id(),
            "title":     result.title,
            "abstract":  result.summary,
            "url":       result.entry_id,
            "published": str(pub_date),
            "authors":   [a.name for a in result.authors[:5]],
            "topic":     topic,
            "week":      period_label,
        }
        papers.append(paper)

    return papers


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    topic     = input("Topic: ").strip() or "large language models"
    frequency = input("Frequency (daily/weekly/biweekly/monthly) [default: weekly]: ").strip() or "weekly"

    query = f'cat:cs.LG AND abs:"{topic}"'

    print(f"\nFetching ArXiv papers for: '{topic}' ({frequency})")
    print(f"Period : {get_period_label(frequency)}")
    print(f"Query  : {query}\n")

    papers = fetch_papers(topic=query, frequency=frequency)

    if not papers:
        print("No papers found.")
    else:
        for p in papers:
            print(f"[{p['week']}] {p['title']}")
            print(f"  → {p['url']}")
            print(f"  Authors: {', '.join(p['authors'])}")
            print()

    print(f"Total: {len(papers)} papers fetched.")