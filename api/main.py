"""
api/main.py — Driftwatch FastAPI backend
"""

import os
import sys
import json
import uuid
import datetime
import threading

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ingestion.arxiv_fetcher import fetch_papers, get_iso_week
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks, get_stats
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report
from delta.comparator import prepare_delta_context
from delta.delta_prompt import build_delta_messages
from delta.report import save_report, load_report, list_reports


app = FastAPI(title="Driftwatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TRACKERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "trackers"
)
os.makedirs(TRACKERS_DIR, exist_ok=True)


# ── Pydantic models ───────────────────────────────────────────────────────────
# Only what the user actually picks — nothing technical exposed

class CreateTrackerRequest(BaseModel):
    topic: str
    frequency: str = "weekly"   # daily / weekly / biweekly / monthly
    report_mode: str = "both"   # summary / delta / both

class AskRequest(BaseModel):
    question: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tracker_path(tracker_id: str) -> str:
    return os.path.join(TRACKERS_DIR, f"{tracker_id}.json")

def _load_tracker(tracker_id: str) -> dict:
    path = _tracker_path(tracker_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Tracker '{tracker_id}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_tracker(tracker: dict):
    path = _tracker_path(tracker["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)

def _all_trackers() -> list[dict]:
    trackers = []
    for fname in os.listdir(TRACKERS_DIR):
        if fname.endswith(".json"):
            fpath = os.path.join(TRACKERS_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                trackers.append(json.load(f))
    trackers.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return trackers

def _build_arxiv_query(plain_topic: str) -> str:
    return f'cat:cs.LG AND abs:"{plain_topic.strip().lower()}"'

def _run_pipeline_background(tracker: dict):
    from scheduler.daemon import run_pipeline
    run_pipeline(tracker)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Driftwatch API running"}


@app.get("/trackers")
def list_trackers():
    return {"trackers": _all_trackers()}


@app.post("/trackers", status_code=201)
def create_tracker(body: CreateTrackerRequest):
    tracker_id = str(uuid.uuid4())[:8]

    tracker = {
        "id":           tracker_id,
        "topic":        body.topic,
        "query":        _build_arxiv_query(body.topic),
        "frequency":    body.frequency,
        "report_mode":  body.report_mode,
        "created_at":   datetime.datetime.now().isoformat(),
        "last_run":     None,
        "last_week":    None,
        "status":       "idle",
        "signal_count": 0,
    }

    _save_tracker(tracker)

    # Fix: thread must be started BEFORE return, not after
    thread = threading.Thread(target=_run_pipeline_background, args=(tracker,))
    thread.daemon = True
    thread.start()

    return {"tracker": tracker}


@app.get("/trackers/{tracker_id}")
def get_tracker(tracker_id: str):
    return {"tracker": _load_tracker(tracker_id)}


@app.delete("/trackers/{tracker_id}")
def delete_tracker(tracker_id: str):
    path = _tracker_path(tracker_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Tracker not found.")
    os.remove(path)
    return {"deleted": tracker_id}


@app.post("/trackers/{tracker_id}/run")
def run_tracker(tracker_id: str):
    tracker = _load_tracker(tracker_id)
    topic   = tracker["topic"]
    query   = tracker["query"]
    mode    = tracker["report_mode"]

    week_current  = get_iso_week(0)
    week_previous = get_iso_week(1)

    results = {
        "tracker_id":    tracker_id,
        "week_current":  week_current,
        "week_previous": week_previous,
        "summary":       None,
        "delta":         None,
        "errors":        []
    }

    tracker["status"]    = "running"
    tracker["last_run"]  = datetime.datetime.now().isoformat()
    tracker["last_week"] = week_current
    _save_tracker(tracker)

    try:
        # Step 1 — Ingest: no max_results limit, fetch everything ArXiv returns
        papers = fetch_papers(topic=query, weeks_ago=0)
        if papers:
            chunks = process_documents(papers)
            save_chunks(chunks)
            tracker["signal_count"] = len(papers)

        # Step 2 — Summary
        if mode in ("summary", "both"):
            retrieved = query_chunks(query_text=topic, week=week_current)
            if retrieved:
                messages     = build_messages(topic=topic, week=week_current, chunks=retrieved)
                summary_text = generate_report(messages)
                results["summary"] = summary_text

        # Step 3 — Delta
        if mode in ("delta", "both"):
            context = prepare_delta_context(
                topic=topic,
                week_current=week_current,
                week_previous=week_previous,
            )
            if context["has_data"]:
                messages   = build_delta_messages(context)
                delta_text = generate_report(messages)
                save_report(
                    topic=topic,
                    week_current=week_current,
                    week_previous=week_previous,
                    report_text=delta_text,
                    context=context
                )
                results["delta"] = {
                    "report":        delta_text,
                    "new_papers":    len(set(c["title"] for c in context["new"])),
                    "continuing":    len(set(c["title"] for c in context["continuing"])),
                    "dropped":       len(set(c["title"] for c in context["dropped"])),
                    "week_current":  week_current,
                    "week_previous": week_previous,
                }
            else:
                results["errors"].append(
                    f"Delta skipped — no data found for {week_previous}. "
                    "Run once more next period to enable delta reports."
                )

        tracker["status"] = "idle"
        _save_tracker(tracker)

    except Exception as e:
        tracker["status"] = "error"
        _save_tracker(tracker)
        results["errors"].append(str(e))

    return results


@app.get("/trackers/{tracker_id}/reports")
def get_reports_list(tracker_id: str):
    tracker = _load_tracker(tracker_id)
    reports = list_reports(tracker["topic"])
    return {"tracker_id": tracker_id, "reports": reports}


@app.get("/trackers/{tracker_id}/report")
def get_latest_report(tracker_id: str):
    tracker = _load_tracker(tracker_id)
    topic   = tracker["topic"]

    week_current  = get_iso_week(0)
    week_previous = get_iso_week(1)

    report = load_report(topic, week_current, week_previous)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for {week_previous} → {week_current}. Run the tracker first."
        )
    return {"tracker_id": tracker_id, "report": report}


@app.post("/trackers/{tracker_id}/ask")
def ask_about_report(tracker_id: str, body: AskRequest):
    tracker = _load_tracker(tracker_id)
    topic   = tracker["topic"]

    week_current  = get_iso_week(0)
    week_previous = get_iso_week(1)

    report = load_report(topic, week_current, week_previous)
    if not report:
        raise HTTPException(status_code=404, detail="No report found. Run the tracker first.")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a research assistant. Answer the user's question "
                "using only the provided research report as context. "
                "Be precise and concise. Do not invent information not in the report."
            )
        },
        {
            "role": "user",
            "content": (
                f"Research report for topic '{topic}' ({week_previous} → {week_current}):\n\n"
                f"{report['report']}\n\n"
                f"Question: {body.question}"
            )
        }
    ]

    answer = generate_report(messages)
    return {"answer": answer, "topic": topic}


@app.get("/stats")
def get_db_stats():
    return get_stats()