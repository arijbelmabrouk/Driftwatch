# Driftwatch

> You don't know what you don't know. Driftwatch fixes that.

Most research tools wait for you to ask a question. Driftwatch runs in the background, watches your field, and tells you what shifted — without you lifting a finger.

---

## The Problem

Every week, hundreds of papers, repos, and discussions reshape the fields we work in. Nobody can keep up. So we either drown in feeds, or fall behind without knowing it.

The real danger isn't the papers you read and disagree with. It's the ones you never saw — the retraction that invalidated your approach, the technique that crossed from another field, the quiet consensus shift that made your architecture outdated.

**Pull tools** (search engines, chatbots, literature databases) only help when you already know what to look for. They can't catch what you didn't know to ask.

**Driftwatch is a push tool.** You register a topic once. It watches forever. At your chosen frequency it delivers one report: *what actually changed.*

---

## How It Works

1. **Register a tracker** — describe your topic in plain language. Driftwatch auto-formats it into a precise ArXiv query behind the scenes. No query syntax required.
2. **Choose your frequency** — daily, weekly, biweekly, or monthly. The system runs on your schedule, not its own. Current implementation defaults to weekly; configurable frequency per tracker is on the roadmap.
3. **Choose your report mode** — weekly summary (what's happening this period), delta report (what changed since last period), or both.
4. **It runs autonomously** — every period it ingests new papers from ArXiv (and later GitHub and HackerNews), chunks and embeds them, and stores them in a local vector database stamped with that period's identifier.
5. **You get a report** — grounded in real sources, saved to disk, never hallucinated.

---

## What Makes It Different

Every individual piece of this system exists somewhere. The combination doesn't.

| Feature | Exists elsewhere? |
|---|---|
| Fetch papers automatically | trivially |
| Summarize papers with LLM | everywhere |
| Detect contradictions | partially (PaperQA2) |
| Track GitHub + forums + papers together | no |
| Persistent memory across periods | no |
| Delta report — what changed vs last period | no |
| Push-based, zero user input after setup | no |
| Cross-disciplinary collision detection | no |

The combination is the innovation.

---

## Report Types

### Weekly Summary
Answers: *"what are papers saying about X this period?"*

Four sections: MAIN THEME · NOTABLE FINDINGS · CONTESTED · OPEN GAP

### Delta Report
Answers: *"what changed about X compared to last period?"*

Four sections: NEW THIS WEEK · STILL ACTIVE · FADING OUT · EMERGING DISPUTE

The delta report is what makes Driftwatch unique. It requires at least two periods of stored data and uses set comparison across ChromaDB to categorize every paper as new, continuing, or dropped — before passing that structured context to the LLM.

---

## Architecture

```
User types plain topic + chooses frequency + chooses report mode
        ↓
auto-format → ArXiv query (cat:cs.LG AND abs:"topic")
        ↓
ArXiv API → raw papers (title, abstract, url, authors)
        ↓
RecursiveCharacterTextSplitter → chunks (~500 chars, 50 overlap)
        ↓
sentence-transformers all-MiniLM-L6-v2 → 384-dim embeddings (local)
        ↓
ChromaDB (persistent, cosine similarity) ← stamped with ISO period identifier
        ↓
        ├── [Summary mode]  similarity search → top 10 chunks → Groq LLM → summary report
        └── [Delta mode]    fetch current + previous period chunks
                            → set comparison (new / continuing / dropped)
                            → Groq LLM → delta report
                            → saved to disk (JSON + .txt)
        ↓
FastAPI backend → React dashboard
```

Everything runs locally. No cloud database. No paid APIs. No subscription.

---

## Technical Decisions

### Chunking — RecursiveCharacterTextSplitter

**Why not fixed-size?** Fixed-size splits by word count and cuts mid-sentence, breaking semantic meaning at boundaries.

**Why not semantic chunker?** Semantic chunking uses embeddings to find meaning boundaries — more intelligent, but 3-4x slower. Unnecessary for batch processing.

**Why Recursive?** It tries to split in priority order: paragraphs → sentences → words → characters. For clean ArXiv abstracts it splits on sentences. For messy GitHub READMEs or HackerNews threads it falls back gracefully. Same chunker handles all future sources without modification.

Settings: `chunk_size=500` characters (~80-100 words), `chunk_overlap=50` characters. Overlap prevents context loss at chunk boundaries.

---

### Embeddings — sentence-transformers / all-MiniLM-L6-v2

**Why not Ollama?** Requires a running server as a separate background process — extra infrastructure, extra failure point, unnecessary for embeddings.

**Why not OpenAI embeddings?** Costs money per token. Violates the free-and-local requirement.

**Why sentence-transformers?** Runs as a Python library import, no server, no API key, no cost. Fully local.

**Why all-MiniLM-L6-v2?** 384-dimensional vectors, 80MB model, fast on CPU. The alternative (`all-mpnet-base-v2`) gives 768 dimensions and better quality but is 2x slower and 4x larger — negligible quality difference at this scale.

---

### Vector Store — ChromaDB

**Why not Pinecone?** Cloud-only. Free tier expires. Violates the local requirement.

**Why not Weaviate?** Requires Docker as a separate running service.

**Why not pgvector?** Requires a full PostgreSQL installation.

**Why ChromaDB?** Pure Python library — `pip install chromadb`, nothing else. Writes to a local folder. Runs in-process. Handles millions of chunks on a laptop. One year of one tracker's data is under 40MB.

**Why cosine similarity, not L2 or inner product?** L2 measures both direction and magnitude — penalizes length differences between short abstracts and long papers unfairly. Cosine similarity measures only the angle between vectors, ignoring magnitude. Two texts that mean the same thing point in the same direction regardless of length. Standard choice for semantic text search.

---

### LLM — Groq API (free tier)

**Why not OpenAI?** Costs money.

**Why not Ollama locally?** Viable fallback, but Groq's free tier is faster (dedicated hardware) and simpler to set up.

**Why Groq specifically?** Free tier gives 14,400 tokens/minute. One report costs ~3,300 tokens total — more than enough for any reasonable report frequency.

Token budget per report:
- 10 retrieved chunks × ~200 tokens = ~2,000 tokens input
- System prompt + instructions = ~500 tokens
- LLM response = ~800 tokens
- **Total: ~3,300 tokens per report**

**Model: `llama-3.1-8b-instant`** — fast, free, 131k context window. Sufficient for summarization and comparison tasks. Swappable to `llama-3.3-70b-versatile` in one line for higher quality.

**Temperature: 0.2** — low, near-deterministic. Reports should be consistent and factual, not creative.

---

### Prompt Design — Six-Component Structure

Both prompts (summary and delta) follow a strict structure: **Role · Task · Context · Reasoning · Stop Conditions · Output**.

The reasoning section is the most important — it tells the LLM to think through each section before writing, which produces more accurate output than asking it to write directly. Stop conditions explicitly ban filler phrases and hallucination. Output format is fixed so reports are consistent across every run.

---

### Report Frequency — User-Configurable

The period identifier stamped on every chunk (`2026-W25` for weekly, `2026-06-21` for daily, `2026-06` for monthly) is the only thing that changes between frequency modes. The delta logic compares period N vs period N-1 regardless of what the period unit is. Current implementation uses weekly periods. Per-tracker configurable frequency (daily / weekly / biweekly / monthly) is a V1 feature.

---

### Delta Logic — Set Comparison

The delta pipeline fetches chunks from two periods out of ChromaDB and runs set operations on paper titles:

- **New** = titles in current period − titles in previous period
- **Continuing** = titles in current period ∩ titles in previous period
- **Dropped** = titles in previous period − titles in current period

This structured categorization is passed to the LLM as context, along with both periods' full chunk text. The LLM never has to figure out what's new — the comparator already did that. The LLM only has to describe what it means.

Reports are saved to disk as both JSON (for the dashboard) and `.txt` (for human reading) under `data/reports/{topic}/{period_current}_vs_{period_previous}/`.

---

### Backend — FastAPI

Thin API layer between the React dashboard and the Python pipeline. Five endpoints: list trackers, create tracker, run tracker, get latest report, ask a question scoped to a report. Tracker configs stored as JSON files in `data/trackers/`. No database required.

---

### Frontend — React + Vite

Single-page dashboard. Tracker cards grid, delta report panel, ask bar scoped to the selected report. All API calls centralized in `api.js` — components never call `fetch()` directly. Dark theme matching the design mockup.

---

### Data Source — ArXiv API

**Why ArXiv first?** Free, no key required, structured data, well-documented Python library. Best source for validating the pipeline before adding messier sources.

**Query format:** `cat:cs.LG AND abs:"topic"` — category filter (cs.LG = Machine Learning) plus abstract phrase match. Plain English input auto-converted by `build_arxiv_query()` in `main.py`.

**Date field:** `result.updated.date()` — more reliable than `published` for weekly filtering since it reflects when the paper actually appeared on ArXiv.

**Period stamp:** Every chunk carries an ISO week string (`2026-W25`). This is the metadata field ChromaDB filters on to retrieve "this period only" vs "last period only."

---

## Project Structure

```
Driftwatch/
├── main.py                        ← interactive entry point, mode selection
├── ingestion/
│   └── arxiv_fetcher.py           ← fetches papers, stamps with period identifier
├── processing/
│   └── chunker_embedder.py        ← recursive chunking + local embeddings
├── storage/
│   └── vector_store.py            ← ChromaDB save + query by topic/period
├── rag/
│   ├── prompt_builder.py          ← assembles summary prompt (6-component structure)
│   └── llm_caller.py              ← sends to Groq, returns report string
├── delta/
│   ├── comparator.py              ← fetches two periods, set comparison logic
│   ├── delta_prompt.py            ← assembles delta prompt (6-component structure)
│   └── report.py                  ← saves reports to disk as JSON + .txt
├── api/
│   └── main.py                    ← FastAPI backend, all endpoints
├── dashboard/                     ← React + Vite frontend
│   └── src/
│       ├── App.jsx                ← main app, state management
│       ├── api.js                 ← all fetch() calls in one place
│       └── components/            ← Sidebar, TrackerCard, ReportPanel, NewTrackerModal
├── scripts/
│   └── seed_week.py               ← dev utility: seed a fake previous period for testing
├── data/                          ← ChromaDB + saved reports (gitignored)
├── requirements.txt
└── .gitignore
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Ingestion | ArXiv API | Free, no key, structured data |
| Chunking | LangChain RecursiveCharacterTextSplitter | Handles all source types |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | Local, free, fast on CPU |
| Vector store | ChromaDB (persistent, cosine) | Local, no server, Python-native |
| LLM | Groq API — llama-3.1-8b-instant | Free, fast, 131k context |
| Delta logic | Set comparison + structured prompting | Period N vs N-1, any frequency |
| Report storage | JSON + .txt on disk | Persistent, dashboard-ready |
| Backend | FastAPI + uvicorn | Lightweight, async, auto-docs |
| Frontend | React + Vite | Fast dev server, component-based |
| Orchestration | LangGraph (upcoming) | Stateful multi-step agentic pipeline |
| Scheduler | APScheduler (upcoming) | Runs at user-chosen frequency |
| Data sources (upcoming) | GitHub API · HackerNews Firebase | All free |

100% free and open source. No paid APIs required.

---

## Project Status

**Phase 1 complete** — Ingestion pipeline
- ArXiv fetcher with ISO period stamping
- RecursiveCharacterTextSplitter + sentence-transformers embeddings
- ChromaDB persistent storage with cosine similarity
- Interactive `main.py` connecting all three

**Phase 2 complete** — RAG layer
- Groq LLM integration (llama-3.1-8b-instant)
- Six-component prompt design
- Weekly summary report generation

**Phase 3 complete** — Delta logic
- Period comparator (set comparison: new / continuing / dropped)
- Delta prompt builder with temporal movement framing
- Report persistence to disk (JSON + .txt)
- Two report modes: summary and delta

**Phase 4 complete** — FastAPI backend + React dashboard
- FastAPI backend with five endpoints
- React dashboard with tracker cards, report panel, ask bar
- Full pipeline triggerable from the browser
- Scoped Q&A on any report via Groq

---

## Roadmap

### MVP (Phases 1–4) — Core Loop
- [x] ArXiv ingestion pipeline with period stamping
- [x] Recursive chunking + local embeddings into ChromaDB
- [x] RAG layer — Groq LLM, summary report generation
- [x] Delta comparison logic — what changed between periods
- [x] LLM-generated delta report with temporal movement framing
- [x] Report persistence to disk
- [x] FastAPI backend
- [x] React dashboard with tracker cards, report viewer, ask bar

### V1 (Phases 5–10) — Multi-Source + Automation
- [ ] Per-tracker configurable frequency (daily / weekly / biweekly / monthly)
- [ ] GitHub trending repos ingestion (READMEs, changelogs, star velocity)
- [ ] HackerNews discussions ingestion (Firebase API)
- [ ] Contradiction detection between papers
- [ ] Instant alerts for CVEs and retractions
- [ ] Email delivery of reports
- [ ] APScheduler daemon (runs at user-chosen frequency, zero manual input)

### V1.5 (Phases 11–14) — Project-Aware Mode
- [ ] VS Code extension — detects open project folder
- [ ] Auto-extract stack from requirements.txt / package.json / README
- [ ] Confirmation prompt before auto-creating tracker
- [ ] Recommendations scoped to your exact project context
- [ ] Alert when a dependency has a relevant update or vulnerability
- [ ] Local background daemon (auto-starts on machine boot)

### V2 (Beyond) — Intelligence Layer
- [ ] Cross-disciplinary collision alerts (technique jumps between fields)
- [ ] Innovation velocity tracking (adoption curves, hype vs production signal)
- [ ] Neo4j knowledge graph for contradiction mapping
- [ ] Multi-tracker dashboard with per-tracker velocity charts

---

## Getting Started

```bash
git clone https://github.com/arijbelmabrouk/Driftwatch.git
cd Driftwatch
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file at the project root:
```
GROQ_API_KEY=your_key_here
```

Start the backend:
```bash
uvicorn api.main:app --reload --port 8000
```

Start the dashboard (separate terminal):
```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

---

## License

MIT