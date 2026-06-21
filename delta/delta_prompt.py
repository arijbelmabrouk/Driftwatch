"""
delta/delta_prompt.py
---------------------
Job: build the prompt for the delta report.
Different from rag/prompt_builder.py — the task here is comparison across
two weeks, not summarization of one week.

The four sections map to temporal movement:
    NEW THIS WEEK     → what appeared that wasn't there before
    STILL ACTIVE      → what carried over from last week
    FADING OUT        → what was there but isn't anymore
    EMERGING DISPUTE  → contradictions between last week and this week
"""

# ── System prompt ─────────────────────────────────────────────────────────────

DELTA_SYSTEM_PROMPT = """
ROLE:
You are a senior research intelligence analyst specializing in tracking how scientific fields evolve over time.
You compare two consecutive periods of research activity and report what shifted.

TASK:
Given paper excerpts from two consecutive weeks, produce a structured delta report that answers:
what is genuinely new, what is continuing, what has faded, and what is now being disputed.

CONTEXT:
- You are part of Driftwatch, an autonomous research monitoring system
- Your reader is a domain expert — a PhD student, R&D engineer, or senior researcher
- You are comparing PREVIOUS WEEK excerpts against CURRENT WEEK excerpts
- The goal is to surface movement and change, not to summarize what is known

REASONING:
Before writing each section, think through:
- NEW THIS WEEK: which topics, techniques, or claims appear in current week but had no presence last week?
- STILL ACTIVE: which themes appear prominently in both weeks — what is the ongoing conversation?
- FADING OUT: which topics were discussed last week but have little or no presence this week?
- EMERGING DISPUTE: do any current week papers contradict or challenge claims from last week?

STOP CONDITIONS:
- Never invent papers or claims not present in the provided excerpts
- Never use filler phrases like "it is worth noting" or "this is an interesting development"
- Never exceed 3 sentences per section
- If a section has nothing to report, write exactly: "Nothing to report this week."

OUTPUT:
Respond using exactly these four headers in this exact order, nothing before or after:

1. NEW THIS WEEK
[your text]

2. STILL ACTIVE
[your text]

3. FADING OUT
[your text]

4. EMERGING DISPUTE
[your text]
"""


# ── Format helpers ────────────────────────────────────────────────────────────

def _format_chunks(chunks: list[dict], label: str) -> str:
    """Formats a list of chunks into a labeled block for the prompt."""
    if not chunks:
        return f"[{label}: no papers found]\n"

    output = f"--- {label} ---\n"
    seen_titles = set()

    for chunk in chunks:
        title = chunk.get("title", "Unknown")
        text  = chunk.get("text", "")

        if title not in seen_titles:
            seen_titles.add(title)
            output += f"\nPaper: {title}\n"

        output += f"{text}\n"

    return output


# ── User message builder ──────────────────────────────────────────────────────

def build_delta_user_message(context: dict) -> str:
    """
    Builds the user message for the delta prompt.

    Args:
        context: the dict returned by comparator.prepare_delta_context()

    Returns:
        Formatted string ready to send as the user message.
    """
    topic         = context["topic"]
    week_current  = context["week_current"]
    week_previous = context["week_previous"]
    all_previous  = context["all_previous"]
    all_current   = context["all_current"]
    new_chunks    = context["new"]
    dropped       = context["dropped"]
    continuing    = context["continuing"]

    # Format the two weeks as labeled blocks
    previous_block = _format_chunks(all_previous, f"PREVIOUS WEEK ({week_previous})")
    current_block  = _format_chunks(all_current,  f"CURRENT WEEK ({week_current})")

    # Summary of what the comparator found
    comparison_summary = (
        f"Comparison summary:\n"
        f"  - New this week (not in {week_previous}): {len(set(c['title'] for c in new_chunks))} papers\n"
        f"  - Continuing from last week: {len(set(c['title'] for c in continuing))} papers\n"
        f"  - Dropped off (was in {week_previous}, gone now): {len(set(c['title'] for c in dropped))} papers\n"
    )

    message = f"""Topic: {topic}
Comparing: {week_previous} → {week_current}

{comparison_summary}

{previous_block}

{current_block}

---

Based on these two weeks of excerpts, write a structured delta report.
Focus on movement and change — not on what is generally known about the topic."""

    return message


def build_delta_messages(context: dict) -> list[dict]:
    """
    Returns the complete messages list ready for the Groq API call.
    """
    return [
        {"role": "system", "content": DELTA_SYSTEM_PROMPT},
        {"role": "user",   "content": build_delta_user_message(context)}
    ]