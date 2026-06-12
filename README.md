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

1. **Register a tracker** — describe your topic in plain language. Driftwatch extracts the signals worth watching.
2. **It runs on a schedule** — every week, it ingests new papers from ArXiv, trending repos from GitHub, and discussions from HackerNews. No input from you.
3. **You get a delta report** — not a summary of everything, a diff of what changed: what's new, what's contested, what gap nobody has filled yet.

---

## What Makes It Different

- **Delta-first** — every report answers "what changed this week?" not "what is known"
- **Contradiction mapping** — surfaces active disputes between papers, not just consensus
- **Cross-disciplinary alerts** — detects when a technique jumps from one field into yours
- **Multi-source** — papers, repos, and practitioner discussions in one unified signal
- **Fully autonomous** — runs on a schedule, zero manual input after setup

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph |
| RAG pipeline | LangChain |
| Embeddings | sentence-transformers (local) |
| Vector store | ChromaDB (persistent) |
| LLM | Groq API (free tier) / Ollama (local) |
| Scheduler | APScheduler |
| Data sources | ArXiv API · GitHub API · HackerNews Firebase API |
| Backend | FastAPI |
| Frontend | React |

100% free and open source. No paid APIs required.

---

## Project Status

🚧 **Active development — Week 1**

Building the core ingestion loop: ArXiv → ChromaDB → delta report.

---

## Roadmap

### MVP (Weeks 1–4) — Core Loop
- [ ] ArXiv ingestion pipeline
- [ ] Chunking + embedding into ChromaDB
- [ ] Weekly delta comparison logic
- [ ] LLM-generated delta report
- [ ] Basic FastAPI + React dashboard

### V1 (Weeks 5–10) — Multi-Source
- [ ] GitHub trending repos ingestion
- [ ] HackerNews discussions ingestion
- [ ] Contradiction detection between papers
- [ ] Instant alerts for CVEs and retractions
- [ ] Email delivery of reports

### V1.5 (Weeks 11–14) — Project-Aware Mode
- [ ] Link a local GitHub repo to Driftwatch
- [ ] Auto-detect stack from requirements.txt / package.json / README
- [ ] Deliver recommendations scoped to your exact project context
- [ ] Alert when a dependency has a relevant update or vulnerability
- [ ] Suggest best papers and tools matching what you are currently building
- [ ] Local background daemon (runs without VS Code open)

### V2 (Beyond) — Intelligence Layer
- [ ] Cross-disciplinary collision alerts
- [ ] Innovation velocity tracking (hype vs adoption curves)
- [ ] Neo4j knowledge graph layer for contradiction mapping
- [ ] Multi-user tracker management

---

## Getting Started

```bash
git clone https://github.com/yourusername/driftwatch.git
cd driftwatch
pip install -r requirements.txt
```

> Full setup instructions coming once the MVP is stable.

---

## License

MIT 