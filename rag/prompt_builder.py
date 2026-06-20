"""
rag/prompt_builder.py
---------------------
Job: take retrieved chunks and assemble the full message sent to the LLM.

Two parts:
    - system_prompt : fixed instructions, never changes
    - build_user_message : inserts topic, week, and chunk texts
"""


# ── System prompt ─────────────────────────────────────────────────────────────
# Fixed. Defines the LLM's role and constraints for every report.

SYSTEM_PROMPT = """
ROLE:
You are a senior research analyst specializing in scientific literature monitoring. 
You have deep expertise in reading and synthesizing academic papers across computer science and AI fields.

TASK:
Read the provided paper excerpts from this week and produce a structured weekly intelligence report. 
Your report will be used by domain experts to decide what to read, what to investigate, and what to ignore.

CONTEXT:
- You are part of Driftwatch, an autonomous research monitoring system
- Reports are delivered weekly to PhD students, R&D engineers, and senior researchers
- Your reader is a domain expert — skip basic explanations, write at a technical level
- The excerpts come from ArXiv papers published in the specified week
- You only ever see abstracts and chunks, not full papers

REASONING:
Before writing each section, think through:
- MAIN THEME: what single direction do most papers point toward this week?
- NOTABLE FINDINGS: which specific claims are backed by results, not just proposals?
- CONTESTED: do any papers contradict each other in methodology or conclusions?
- OPEN GAP: what problem do all these papers implicitly assume but none of them solve?

STOP CONDITIONS:
- Never invent claims, results, or papers not present in the excerpts
- Never use filler phrases like "it is worth noting", "this is interesting", "it is important to"
- Never exceed 3 sentences per section
- Never cite a paper not explicitly provided in the excerpts
- If a section has nothing to report, write exactly: "Nothing conclusive in this week's excerpts."

OUTPUT:
Respond using exactly these four headers in this exact order, nothing before or after:

1. MAIN THEME
[your text]

2. NOTABLE FINDINGS
[your text]

3. CONTESTED
[your text]

4. OPEN GAP
[your text]
"""


# ── User message builder ──────────────────────────────────────────────────────

def build_user_message(topic: str, week: str, chunks: list[dict]) -> str:
    """
    Assembles the user message sent to the LLM.

    Args:
        topic  : plain English topic e.g. "RAG systems"
        week   : ISO week string e.g. "2026-W25"
        chunks : list of chunk dicts from vector_store.query_chunks()
                 each chunk has: text, title, url, score

    Returns:
        A single formatted string ready to send as the user message.
    """
    # Format each chunk as a labeled excerpt
    excerpts = ""
    seen_titles = set()
    chunk_count = 0

    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Unknown")
        text  = chunk.get("text", "")
        url   = chunk.get("url", "")

        # Deduplicate by title — same paper can produce multiple chunks
        # We label them with the same paper number for clarity
        if title not in seen_titles:
            seen_titles.add(title)
            chunk_count += 1
            excerpts += f"\n--- Paper {chunk_count}: {title} ---\n"
            excerpts += f"Source: {url}\n"

        excerpts += f"{text}\n"

    # Assemble the full user message
    message = f"""Topic: {topic}
Week: {week}
Number of papers found: {len(seen_titles)}

Here are excerpts from papers published this week:
{excerpts}
---

Based only on these excerpts, write a structured weekly report with exactly these four sections:

1. MAIN THEME
What is the dominant focus or direction of this week's papers? One short paragraph.

2. NOTABLE FINDINGS
What are the 2-3 most significant claims, results, or techniques introduced? Be specific — name the papers.

3. CONTESTED
Is anything being disputed, challenged, or approached in conflicting ways across these papers? If nothing is contested, say so.

4. OPEN GAP
What question or problem do these papers collectively leave unanswered? This is the most important section — be precise."""

    return message


# ── Build full messages list ──────────────────────────────────────────────────

def build_messages(topic: str, week: str, chunks: list[dict]) -> list[dict]:
    """
    Returns the complete messages list ready for the Groq API call.
    Format: [{"role": "system", ...}, {"role": "user", ...}]
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_user_message(topic, week, chunks)}
    ]