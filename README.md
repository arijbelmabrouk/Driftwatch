# Driftwatch

> You don't know what you don't know. Driftwatch fixes that.

Most research tools wait for you to ask a question. Driftwatch runs in the background, watches your field, and tells you what shifted — without you lifting a finger.

---

## The Problem

Every week, hundreds of papers, repos, and discussions reshape the fields we work in. Nobody can keep up. So we either drown in feeds, or fall behind without knowing it.

The real danger isn't the papers you read and disagree with. It's the ones you never saw — the retraction that invalidated your approach, the technique that crossed from another field, the quiet consensus shift that made your architecture outdated.

**Pull tools** (search engines, chatbots, literature databases) only help when you already know what to look for. They can't catch what you didn't know to ask.

**Driftwatch is a push tool.** You register a topic once. It watches forever. Every week it delivers one report: *what actually changed.*

---

## How It Works

1. **Register a tracker** — describe your topic in plain language. Driftwatch auto-formats it into a precise ArXiv query behind the scenes. No query syntax required.
2. **It runs on a schedule** — every week, it ingests new papers from ArXiv (and later GitHub and HackerNews), chunks and embeds them, and stores them in a local vector database stamped with that week's identifier.
3. **You get a delta report** — not a summary of everything known, a diff of what changed: what's genuinely new, what's incremental, what's actively contested, and what gap nobody has answered yet.

---

## What Makes It Different

Every individual piece of this system exists somewhere. The combination doesn't.

| Feature | Exists elsewhere? |
|---|---|
| Fetch papers automatically | ✅ trivially |
| Summarize papers with LLM | ✅ everywhere |
| Detect contradictions | ✅ partially (PaperQA2) |
| Track GitHub + forums + papers together | ❌ |
| Persistent memory across weeks | ❌ |
| Delta report — what changed vs last week | ❌ |
| Push-based, zero user input after setup | ❌ |
| Cross-disciplinary collision detection | ❌ |

The combination is the innovation.

---

## Architecture

```
User types plain topic
        ↓
auto-format → ArXiv query (cat:cs.LG AND abs:"topic")
        ↓
ArXiv API → raw papers (title, abstract, url, authors)
        ↓
RecursiveCharacterTextSplitter → chunks (~500 chars, 50 overlap)
        ↓
sentence-transformers all-MiniLM-L6-v2 → 384-dim embeddings (local)
        ↓
ChromaDB (persistent, cosine similarity) ← stamped with ISO week
        ↓
similarity search → top 10 chunks retrieved
        ↓
Groq LLM (free) → delta report generated (~3,300 tokens total)
        ↓
Dashboard / terminal output
```

Everything runs locally. No cloud database. No paid APIs. No subscription.

---

## Technical Decisions

### Chunking — RecursiveCharacterTextSplitter

**Why not fixed-size?** Fixed-size splits by word count and cuts mid-sentence, breaking semantic meaning at boundaries.

**Why not semantic chunker?** Semantic chunking uses embeddings to find meaning boundaries — more intelligent, but 3-4x slower. Unnecessary for weekly batch processing.

**Why Recursive?** It tries to split in priority order: paragraphs → sentences → words → characters. For clean ArXiv abstracts it splits on sentences. For messy GitHub READMEs or HackerNews threads it falls back gracefully. Same chunker handles all future sources without modification.

Settings: `chunk_size=500` characters (~80-100 words), `chunk_overlap=50` characters. Overlap prevents context loss at chunk boundaries.

---

### Embeddings — sentence-transformers / all-MiniLM-L6-v2

**Why not Ollama?** Ollama requires a running server as a separate background process — extra infrastructure, extra failure point, unnecessary for embeddings.

**Why not OpenAI embeddings?** Costs money per token. Violates the free-and-local requirement.

**Why sentence-transformers?** Runs as a Python library import, no server, no API key, no cost. Fully local.

**Why all-MiniLM-L6-v2?** Produces 384-dimensional vectors. 80MB model size. Fast on CPU. The alternative (`all-mpnet-base-v2`) gives 768 dimensions and higher quality but is 2x slower and 4x larger — negligible quality difference at this scale doesn't justify the tradeoff.

---

### Vector Store — ChromaDB

**Why not Pinecone?** Cloud-only. Free tier expires. Violates the local requirement.

**Why not Weaviate?** Requires Docker as a separate running service.

**Why not pgvector?** Requires a full PostgreSQL installation.

**Why ChromaDB?** Pure Python library — `pip install chromadb`, nothing else. Writes to a local folder. Runs in-process. Handles millions of chunks on a laptop. One year of one tracker's data is under 40MB.

**Why cosine similarity, not L2 or inner product?** L2 (euclidean distance) measures both direction and magnitude. For text, a short abstract and a long paper on the same topic have different magnitudes — L2 penalizes length differences unfairly. Inner product has similar issues. Cosine similarity measures only the angle between vectors, ignoring magnitude entirely. Two texts that mean the same thing point in the same direction regardless of their length. Correct measure for semantic text search.

---

### LLM — Groq API (free tier)

**Why not OpenAI?** Costs money.

**Why not Ollama locally?** Viable option, but Groq's free tier is faster (runs on dedicated hardware) and simpler to set up for the LLM layer. Ollama remains a fallback for fully offline use.

**Why Groq specifically?** Free tier gives 14,400 tokens/minute. One delta report costs ~3,300 tokens. That's 4 reports per minute for free — more than enough for a weekly scheduler.

Token budget per report:
- 10 retrieved chunks × ~200 tokens each = ~2,000 tokens
- System prompt + instructions = ~500 tokens
- LLM response (the report) = ~800 tokens
- **Total: ~3,300 tokens per report**

---

### Data Source — ArXiv API

**Why ArXiv first?** Free, no API key required, well-documented Python library, returns structured data (title, abstract, date, ID). Ideal for validating the pipeline before adding messier sources.

**Query format:** `cat:cs.LG AND abs:"topic"` — category filter ensures ML/CS papers only, abstract filter ensures topic relevance. Plain English input is auto-converted to this format by `build_arxiv_query()` in `main.py`.

**Date stamping:** Uses `result.updated.date()` rather than `result.published.date()` — more reliable for weekly filtering since `updated` reflects when the paper actually appeared on ArXiv.

**Week identifier:** Every document and chunk is stamped with an ISO week string (`2026-W25`). This is the critical metadata field that makes the delta comparison possible — ChromaDB filters by this field to retrieve "this week only" vs "last week only" for comparison.

---

## Project Structure

```
Driftwatch/
├── main.py                    ← interactive entry point, full pipeline
├── ingestion/
│   └── arxiv_fetcher.py       ← fetches papers from ArXiv, week-stamps each one
├── processing/
│   └── chunker_embedder.py    ← chunks text, embeds into 384-dim vectors
├── storage/
│   └── vector_store.py        ← saves to ChromaDB, queries by topic + week
├── rag/                       ← Week 2: retrieval + LLM generation
├── delta/                     ← Week 3: week-over-week comparison logic
├── api/                       ← Week 4: FastAPI backend
├── dashboard/                 ← Week 4: React frontend
├── data/                      ← ChromaDB lives here (gitignored)
├── requirements.txt
└── .gitignore
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Ingestion | ArXiv API | Free, no key, structured data |
| Chunking | LangChain RecursiveCharacterTextSplitter | Handles all source types (papers, READMEs, threads) |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | Local, free, fast on CPU |
| Vector store | ChromaDB (persistent, cosine) | Local, no server, Python-native |
| LLM | Groq API (free tier) | Free, fast, ~3,300 tokens per report |
| Orchestration | LangGraph | Stateful multi-step agentic pipeline |
| Scheduler | APScheduler | Weekly cron, zero manual input |
| Data sources | ArXiv · GitHub API · HackerNews Firebase | All free, no key required for ArXiv/HN |
| Backend | FastAPI | Lightweight, async |
| Frontend | React + D3.js | Dashboard + contradiction graph visualization |

100% free and open source. No paid APIs required to run the full system.

---

## Project Status

🚧 **Active development — Week 2**

Week 1 complete: full ingestion pipeline working end-to-end.
- ArXiv fetcher with ISO week stamping ✅
- RecursiveCharacterTextSplitter + sentence-transformers embeddings ✅
- ChromaDB persistent storage with cosine similarity ✅
- Interactive `main.py` connecting all three ✅

Now building: RAG layer — Groq LLM integration and delta report generation.

---

## Roadmap

### MVP (Weeks 1–4) — Core Loop
- [x] ArXiv ingestion pipeline with week stamping
- [x] Chunking (recursive) + embedding (local) into ChromaDB
- [ ] RAG layer — Groq LLM integration, basic summary generation
- [ ] Weekly delta comparison logic (W25 vs W24)
- [ ] LLM-generated structured delta report
- [ ] Basic FastAPI + React dashboard

### V1 (Weeks 5–10) — Multi-Source
- [ ] GitHub trending repos ingestion (READMEs, changelogs, star velocity)
- [ ] HackerNews discussions ingestion (Firebase API)
- [ ] Contradiction detection between papers
- [ ] Instant alerts for CVEs and retractions
- [ ] Email delivery of reports
- [ ] APScheduler daemon (runs weekly, zero user input)

### V1.5 (Weeks 11–14) — Project-Aware Mode
- [ ] VS Code extension — detects open project folder
- [ ] Auto-extract stack from requirements.txt / package.json / README
- [ ] Confirmation prompt before creating tracker automatically
- [ ] Deliver recommendations scoped to your exact project context
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
python main.py
```

> Groq API key required for Week 2+ features. Get one free at console.groq.com.

---

## License

MIT