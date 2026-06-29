# Driftwatch

> You don't know what you don't know. Driftwatch fixes that.

Most research tools wait for you to ask a question. Driftwatch runs in the background, watches your field, and tells you what shifted — without you lifting a finger.

---

## The Problem

Every week, hundreds of papers, repos, and discussions reshape the fields we work in. Nobody can keep up. So we either drown in feeds, or fall behind without knowing it.

The real danger isn't the papers you read and disagree with. It's the ones you never saw — the retraction that invalidated your approach, the technique that crossed from another field, the quiet consensus shift that made your architecture outdated.

**Pull tools** (search engines, chatbots, literature databases) only help when you already know what to look for. They can't catch what you didn't know to ask.

**Driftwatch is a push tool.** You register a topic once. It watches forever. At your chosen frequency it delivers one report: *what actually changed* — straight to your inbox.

---

## How It Works

1. **Create an account** — register with your email. Driftwatch is a multi-user platform. Every tracker and report is scoped to your account.
2. **Register a tracker** — describe your topic in plain language. Driftwatch auto-formats it into precise queries for each source behind the scenes. No query syntax required.
3. **Choose your frequency** — daily, weekly, biweekly, or monthly. Each tracker runs on its own schedule. The daemon checks every hour and runs any tracker that is due.
4. **Choose your report mode** — summary (what's happening this period), delta (what changed since last period), or both.
5. **It runs autonomously** — the background daemon ingests new content from ArXiv, GitHub, and HackerNews, chunks and embeds everything, and stores it in a local vector database stamped with that period's identifier. No manual input required after setup.
6. **You get a report** — delivered to your inbox automatically. Full report text in the email body — no clicking through to a dashboard required. The dashboard is also available for browsing history and asking follow-up questions.

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
| Full report delivered to inbox automatically | no |
| Multi-user platform with per-account tracker isolation | no |
| Clickable bibliography per report | no |

The combination is the innovation.

---

## Report Types

### Summary
Answers: *"what are papers, repos, and discussions saying about X this period?"*

Four sections: MAIN THEME · NOTABLE FINDINGS · CONTESTED · OPEN GAP

### Delta Report
Answers: *"what changed about X compared to last period?"*

Four sections: NEW THIS WEEK · STILL ACTIVE · FADING OUT · EMERGING DISPUTE

The delta report is what makes Driftwatch unique. It requires at least two periods of stored data and uses set comparison across ChromaDB to categorize every source as new, continuing, or dropped — before passing that structured context to the LLM.

Each report ends with a **Sources** section — every ArXiv paper, GitHub repo, and HackerNews thread that informed the report, tagged by source type and linking directly to the original.

---

## Architecture

```
User registers → logs in → creates tracker (topic + frequency + mode)
        ↓
Daemon checks every hour → finds due trackers per user
        ↓
        ├── ArXiv API    → papers (title, abstract, url, authors)
        ├── GitHub API   → repos (name, description, README, stars)
        └── HackerNews   → stories + top comments (Algolia Search API)
        ↓
Merge all documents from all three sources
        ↓
RecursiveCharacterTextSplitter → chunks (~500 chars, 50 overlap)
        ↓
sentence-transformers all-MiniLM-L6-v2 → 384-dim embeddings (local)
        ↓
ChromaDB (persistent, cosine similarity) ← stamped with period identifier + source tag
        ↓
        ├── [Summary mode]  similarity search → top chunks → Groq LLM → summary report
        └── [Delta mode]    fetch current + previous period chunks
                            → set comparison (new / continuing / dropped)
                            → Groq LLM → delta report
                            → saved to disk (JSON + .txt) with sources list
        ↓
        ├── FastAPI backend → React dashboard (summary + delta + clickable bibliography)
        └── Gmail SMTP → full report emailed to user's registered address
```

Everything runs locally. No cloud database. No paid APIs. No subscription.

---

## Technical Decisions

### Chunking — RecursiveCharacterTextSplitter

**Why not fixed-size?** Fixed-size splits by word count and cuts mid-sentence, breaking semantic meaning at boundaries.

**Why not semantic chunker?** Semantic chunking uses embeddings to find meaning boundaries — more intelligent, but 3-4x slower. Unnecessary for batch processing.

**Why Recursive?** It tries to split in priority order: paragraphs → sentences → words → characters. For clean ArXiv abstracts it splits on sentences. For messy GitHub READMEs or HackerNews threads it falls back gracefully. Same chunker handles all sources without modification.

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
- Retrieved chunks × ~200 tokens = ~2,000 tokens input
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

### Data Sources

**ArXiv API** — academic papers. Free, no key required, structured data. Query format: `cat:cs.LG AND abs:"topic"`. Every paper is stamped with the tracker's period identifier and `source: arxiv`.

**GitHub API** — trending repos. Requires a free token (no scopes needed). Searches repo name and description with `stars:>100` quality filter. Fetches README content truncated to 1,500 characters. Every repo is stamped with the same period identifier and `source: github`.

**HackerNews** — community discussions. Uses the official Algolia HN Search API (free, no key required). Searches stories matching the topic within the current period using Unix timestamp filters. Fetches story title, self-text, and top 5 comments per story for rich discussion signal. Every story is stamped with the same period identifier and `source: hn`.

All three fetchers share a single source of truth for period label calculation — `github_fetcher` and `hn_fetcher` both import period helpers from `arxiv_fetcher.py` to guarantee identical stamps across all sources in ChromaDB.

Query design is kept separate per fetcher — ArXiv, GitHub, and HackerNews have different query syntaxes and different search semantics. Each fetcher owns its own query logic internally.

---

### Authentication — JWT + SQLite

**User model:** Email + hashed password stored in a local SQLite database (`data/driftwatch.db`). Password hashing uses PBKDF2-HMAC-SHA256 with a random salt — no external auth library required.

**Tokens:** Pure Python JWT implementation using HMAC-SHA256. Tokens expire after 24 hours (configurable via `JWT_EXPIRATION_SECONDS` in `.env`). The secret key is set via `JWT_SECRET` in `.env`.

**Why not a third-party auth library?** The auth requirements are simple — email/password login, JWT tokens, no OAuth. A pure Python implementation is smaller, has no external dependencies, and is fully auditable.

**Multi-user isolation:** Every tracker is stored with a `user_id` foreign key. All API endpoints verify the JWT and filter data by the authenticated user. Users can only see, run, and delete their own trackers.

---

### Email Delivery — Gmail SMTP

Reports are delivered automatically to the user's registered email address after every pipeline run. No manual action required.

**Delivery:** Python's built-in `smtplib` with STARTTLS on port 587. Gmail app password stored in `.env` — your real Gmail password is never used.

**Email content:** Full report text in the plain-text body — summary and delta sections separated by clear headers. No HTML, no click-through required. The entire intelligence is in the email.

**Recipient:** The user's registered account email. Not a global config — each user receives reports only for their own trackers.

**Sender credentials** stored in `.env`:
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
GMAIL_SENDER_EMAIL=your-sender@gmail.com
GMAIL_SENDER_PASSWORD=your-app-password
```

---

### Report Frequency — User-Configurable Per Tracker

Each tracker has its own frequency setting. The period identifier stamped on every chunk adapts to that frequency:

- daily → `2026-06-26`
- weekly → `2026-W26`
- biweekly → `2026-W26` (runs every two weeks)
- monthly → `2026-06`

The delta logic compares period N vs period N-1 regardless of the time unit. The daemon checks every hour and runs any tracker whose last run was more than `frequency_days` ago — 1 for daily, 7 for weekly, 14 for biweekly, 30 for monthly.

---

### Delta Logic — Set Comparison

The delta pipeline fetches chunks from two periods out of ChromaDB and runs set operations on source titles:

- **New** = titles in current period − titles in previous period
- **Continuing** = titles in current period ∩ titles in previous period
- **Dropped** = titles in previous period − titles in current period

This structured categorization is passed to the LLM as context. The LLM never has to figure out what's new — the comparator already did that. The LLM only has to describe what it means.

Reports are saved to disk as both JSON (for the dashboard) and `.txt` (for human reading) under `data/reports/{topic}/{period_current}_vs_{period_previous}/`. The JSON includes a `sources` array with title, url, and source type for every document that informed the report.

---

### Scheduler Daemon — APScheduler

`scheduler/daemon.py` runs as a background process. On start it runs an immediate check, then checks every hour. It queries the SQLite database for all users, then for each user loads their trackers and runs any that are due.

After each successful pipeline run, the daemon:
1. Saves the report to disk (JSON + .txt)
2. Emails the full report to the user's registered address via Gmail SMTP

The daemon is independent of the FastAPI server and the dashboard. When a new tracker is created from the dashboard, the API also fires the pipeline immediately in a background thread.

---

### Backend — FastAPI + SQLite

Authentication endpoints (`/auth/register`, `/auth/login`, `/auth/me`) handle user creation and JWT issuance. All tracker endpoints require a valid Bearer token and return only data belonging to the authenticated user. Tracker configuration is persisted in `data/driftwatch.db`.

---

### Frontend — React + Vite

Single-page dashboard with a login/register screen before the main view. After authentication the JWT is stored in `localStorage` and included in all API requests automatically. The dashboard shows tracker cards, summary and delta reports, a clickable sources bibliography, and an ask bar for follow-up questions scoped to the current report.

---

## Project Structure

```
Driftwatch/
├── main.py                        ← interactive entry point, mode selection
├── auth.py                        ← password hashing + JWT token helpers
├── database.py                    ← SQLite schema, user + tracker persistence
├── ingestion/
│   ├── arxiv_fetcher.py           ← fetches papers, frequency-aware period stamping
│   ├── github_fetcher.py          ← fetches repos, imports period helpers from arxiv_fetcher
│   └── hn_fetcher.py              ← fetches HN stories via Algolia API
├── processing/
│   └── chunker_embedder.py        ← recursive chunking + local embeddings
├── storage/
│   └── vector_store.py            ← ChromaDB save + smart retrieval
├── rag/
│   ├── prompt_builder.py          ← assembles summary prompt (6-component structure)
│   └── llm_caller.py              ← sends to Groq, returns report string
├── delta/
│   ├── comparator.py              ← fetches two periods, set comparison logic
│   ├── delta_prompt.py            ← assembles delta prompt (6-component structure)
│   └── report.py                  ← saves summary + delta reports to disk as JSON with sources
├── notifications/
│   └── emailer.py                 ← Gmail SMTP delivery, builds and sends full report email
├── api/
│   └── main.py                    ← FastAPI backend, auth + tracker endpoints
├── scheduler/
│   └── daemon.py                  ← background daemon, per-user pipeline, email delivery
├── dashboard/                     ← React + Vite frontend
│   └── src/
│       ├── App.jsx                ← main app, auth state, session restore
│       ├── api.js                 ← all fetch() calls with automatic Bearer token
│       └── components/
│           ├── AuthScreen.jsx     ← login / register UI
│           ├── Sidebar.jsx
│           ├── TrackerCard.jsx
│           ├── ReportPanel.jsx
│           └── NewTrackerModal.jsx
├── scripts/
│   ├── seed_week.py               ← dev utility: seed a fake previous period for testing
│   └── migrate_trackers.py        ← migrates existing JSON trackers into SQLite
├── tests/
│   └── test_emailer.py            ← unit tests for email builder and SMTP settings
├── data/                          ← ChromaDB + saved reports + SQLite DB (gitignored)
├── requirements.txt
└── .gitignore
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Ingestion — papers | ArXiv API | Free, no key, structured data |
| Ingestion — repos | GitHub Search API | Free token, real adoption signal |
| Ingestion — discussions | HackerNews Algolia API | Free, no key, practitioner signal |
| Chunking | LangChain RecursiveCharacterTextSplitter | Handles clean abstracts and messy READMEs |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | Local, free, fast on CPU |
| Vector store | ChromaDB (persistent, cosine) | Local, no server, Python-native |
| LLM | Groq API — llama-3.1-8b-instant | Free, fast, 131k context |
| Delta logic | Set comparison + structured prompting | Period N vs N-1, any frequency |
| Report storage | JSON + .txt on disk | Persistent, dashboard-ready, includes sources list |
| Email delivery | Gmail SMTP via smtplib | Full report in email body, zero click-through |
| Auth | Pure Python JWT + PBKDF2 | No external auth library, fully auditable |
| Persistence | SQLite via database.py | User + tracker storage, multi-user isolation |
| Scheduler | APScheduler | Hourly check, frequency-aware, per-user |
| Backend | FastAPI + uvicorn | Lightweight, async, auto-docs |
| Frontend | React + Vite | Fast dev server, component-based |
| Orchestration | LangGraph (upcoming) | Stateful multi-step agentic pipeline |

100% free and open source. No paid APIs required.

---

## Project Status

**Phase 1 complete** — Ingestion pipeline
- ArXiv fetcher with frequency-aware period stamping (daily / weekly / biweekly / monthly)
- RecursiveCharacterTextSplitter + sentence-transformers embeddings
- ChromaDB persistent storage with cosine similarity

**Phase 2 complete** — RAG layer
- Groq LLM integration (llama-3.1-8b-instant)
- Six-component prompt design
- Summary report generation

**Phase 3 complete** — Delta logic
- Period comparator (set comparison: new / continuing / dropped)
- Delta prompt builder with temporal movement framing
- Report persistence to disk (JSON + .txt)
- Two report modes: summary and delta

**Phase 4 complete** — FastAPI backend + React dashboard
- FastAPI backend with full endpoint set
- React dashboard with tracker cards, report panel, ask bar
- Both summary and delta rendered when mode is "both"
- Scoped Q&A on any report via Groq

**Phase 5 complete** — Scheduler daemon + frequency-aware periods
- APScheduler daemon running hourly checks
- Per-tracker configurable frequency (daily / weekly / biweekly / monthly)
- Immediate pipeline run on tracker creation via background thread

**Phase 6 complete** — GitHub ingestion + sources bibliography
- GitHub Search API fetcher with star filter and README truncation
- Sources bibliography saved with every report and rendered in dashboard
- Clickable bibliography with color-coded arxiv/github source tags

**Phase 7 complete** — HackerNews ingestion
- Algolia HN Search API — stories + top 5 comments per story
- Merged into the same pipeline alongside ArXiv and GitHub
- HN sources included in bibliography

**Phase 8 complete** — Multi-user platform + email delivery
- SQLite database with users and trackers tables
- User registration and login with PBKDF2 password hashing
- Pure Python JWT authentication — no external auth library
- All API endpoints scoped to the authenticated user
- React dashboard with login/register screen and session restore
- Daemon loops per user — each user's trackers run independently
- Gmail SMTP email delivery — full report text in email body after every pipeline run
- Recipient email comes from user's registered account, not hardcoded config

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

### V1 (Phases 5–8) — Automation + Multi-Source + Delivery
- [x] Per-tracker configurable frequency (daily / weekly / biweekly / monthly)
- [x] APScheduler daemon (runs at user-chosen frequency, zero manual input)
- [x] Immediate pipeline run on tracker creation
- [x] GitHub trending repos ingestion
- [x] HackerNews discussions ingestion (Algolia API)
- [x] Clickable sources bibliography per report
- [x] Multi-user platform with SQLite + JWT auth
- [x] Email delivery — full report to user's inbox after every run
- [ ] Contradiction detection between papers
- [ ] Instant alerts for CVEs and retractions

### V1.5 (Phases 9–12) — Project-Aware Mode
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
GROQ_API_KEY=your_groq_key_here
GITHUB_TOKEN=your_github_token_here
JWT_SECRET=pick-any-long-random-string

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
GMAIL_SENDER_EMAIL=your-sender@gmail.com
GMAIL_SENDER_PASSWORD=your-gmail-app-password
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

Get a free GitHub token at [github.com/settings/tokens](https://github.com/settings/tokens) — no scopes needed.

Get a Gmail app password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — requires 2-Step Verification enabled.

Start the backend:
```bash
uvicorn api.main:app --reload --port 8000 --reload-exclude "venv"
```

Start the dashboard (separate terminal):
```bash
cd dashboard
npm install
npm run dev
```

Start the daemon (separate terminal — runs pipelines and sends emails automatically):
```bash
python scheduler/daemon.py
```

Open `http://localhost:5173`, register an account, and create your first tracker.

---

## License

MIT