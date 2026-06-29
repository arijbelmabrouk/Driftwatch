"""
api/main.py — Driftwatch FastAPI backend
"""

import os
import sys
import json
import uuid
import datetime
import threading
import sqlite3
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ingestion.arxiv_fetcher import (
    fetch_papers,
    get_period_label,
    get_previous_period_label,
)
from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, query_chunks, get_stats
from rag.prompt_builder import build_messages
from rag.llm_caller import generate_report
from delta.comparator import prepare_delta_context
from delta.delta_prompt import build_delta_messages
from delta.report import save_report, load_report, save_summary, load_summary, list_reports
from ingestion.github_fetcher import fetch_github_repos
from ingestion.hn_fetcher import fetch_hn_stories

import database
import auth

database.init_db()


def _run_pipeline_background(tracker: dict):
    from scheduler.daemon import run_pipeline
    user = database.get_user_by_id(tracker.get("user_id"))
    run_pipeline(tracker, user)


app = FastAPI(title="Driftwatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CreateTrackerRequest(BaseModel):
    topic: str
    frequency: str = "weekly"
    report_mode: str = "both"

class AskRequest(BaseModel):
    question: str

class AuthRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _load_tracker(tracker_id: str, user_id: str) -> dict:
    tracker = database.get_tracker(tracker_id, user_id)
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Tracker '{tracker_id}' not found.")
    return tracker


def _save_tracker(tracker: dict):
    database.save_tracker(tracker)


def _all_trackers(user_id: str) -> list[dict]:
    return database.list_trackers(user_id)


def _build_arxiv_query(plain_topic: str) -> str:
    return f'cat:cs.LG AND abs:"{plain_topic.strip().lower()}"'


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    payload = auth.verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = database.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user




@app.get("/")
def root():
    return {"status": "Driftwatch API running"}


@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(body: AuthRequest):
    if database.get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    user_id = str(uuid.uuid4())
    password_hash = auth.hash_password(body.password)

    try:
        database.create_user(user_id, body.email, password_hash)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered.")

    token = auth.create_access_token(user_id=user_id, email=body.email)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", response_model=TokenResponse)
def login(body: AuthRequest):
    user = database.get_user_by_email(body.email)
    if not user or not auth.verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    database.update_user_last_login(user["id"])
    token = auth.create_access_token(user_id=user["id"], email=user["email"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me")
def auth_me(current_user=Depends(get_current_user)):
    return {
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "created_at": current_user["created_at"],
        }
    }


@app.get("/trackers")
def list_trackers(current_user=Depends(get_current_user)):
    return {"trackers": _all_trackers(current_user["id"])}


@app.post("/trackers", status_code=201)
def create_tracker(body: CreateTrackerRequest, current_user=Depends(get_current_user)):
    tracker_id = str(uuid.uuid4())[:8]

    tracker = {
        "id":           tracker_id,
        "user_id":      current_user["id"],
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

    database.create_tracker(tracker)

    # Spawn a daemon thread to run the pipeline in background and return immediately
    thread = threading.Thread(target=_run_pipeline_background, args=(tracker,))
    thread.daemon = True
    thread.start()

    return {"tracker": tracker}


@app.get("/trackers/{tracker_id}")
def get_tracker(tracker_id: str, current_user=Depends(get_current_user)):
    return {"tracker": _load_tracker(tracker_id, current_user["id"])}


@app.delete("/trackers/{tracker_id}")
def delete_tracker(tracker_id: str, current_user=Depends(get_current_user)):
    deleted = database.delete_tracker(tracker_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Tracker not found.")
    return {"deleted": tracker_id}


@app.post("/trackers/{tracker_id}/run")
def run_tracker(tracker_id: str, current_user=Depends(get_current_user)):
    tracker = _load_tracker(tracker_id, current_user["id"])
    topic   = tracker["topic"]
    query   = tracker["query"]
    mode    = tracker["report_mode"]

    week_current  = get_period_label(tracker["frequency"])
    week_previous = get_previous_period_label(tracker["frequency"])

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
        # Step 1 — Ingest from ArXiv
        papers = fetch_papers(topic=query, frequency=tracker["frequency"])

        # Step 1b — Ingest from GitHub
        github_docs = fetch_github_repos(
            topic=topic,
            frequency=tracker["frequency"],
        )

        # Step 1c — Ingest from Hacker News
        hn_docs = fetch_hn_stories(
            topic=topic,
            frequency=tracker["frequency"],
        )

        # Merge all sources
        all_documents = papers + github_docs + hn_docs

        if all_documents:
            chunks = process_documents(all_documents)
            save_chunks(chunks)
            tracker["signal_count"] = len(all_documents)

        # Step 2 — Summary
        if mode in ("summary", "both"):
            retrieved = query_chunks(query_text=topic, week=week_current)
            if retrieved:
                messages     = build_messages(topic=topic, week=week_current, chunks=retrieved)
                summary_text = generate_report(messages)
                # Save to disk so it can be loaded back on next mount
                save_summary(topic=topic, week_current=week_current, report_text=summary_text, chunks=retrieved)
                # Return the same structure as load_summary so frontend can consume it
                results["summary"] = load_summary(topic, week_current)

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
                # Return the saved JSON structure so frontend rendering matches saved files
                results["delta"] = load_report(topic, week_current, week_previous)
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
def get_reports_list(tracker_id: str, current_user=Depends(get_current_user)):
    tracker = _load_tracker(tracker_id, current_user["id"])
    reports = list_reports(tracker["topic"])
    return {"tracker_id": tracker_id, "reports": reports}


@app.get("/trackers/{tracker_id}/report")
def get_latest_report(tracker_id: str, current_user=Depends(get_current_user)):
    """
    Returns both summary and delta for the current period.
    Each key is null if that report type doesn't exist or wasn't generated.
    """
    tracker = _load_tracker(tracker_id, current_user["id"])
    topic   = tracker["topic"]

    week_current  = get_period_label(tracker["frequency"])
    week_previous = get_previous_period_label(tracker["frequency"])

    summary = load_summary(topic, week_current)
    delta   = load_report(topic, week_current, week_previous)

    return {
        "tracker_id": tracker_id,
        "summary":    summary,
        "delta":      delta,
    }


@app.post("/trackers/{tracker_id}/ask")
def ask_about_report(tracker_id: str, body: AskRequest, current_user=Depends(get_current_user)):
    tracker = _load_tracker(tracker_id, current_user["id"])
    topic   = tracker["topic"]

    week_current  = get_period_label(tracker["frequency"])
    week_previous = get_previous_period_label(tracker["frequency"])

    # Use delta report as context if available, else summary
    delta   = load_report(topic, week_current, week_previous)
    summary = load_summary(topic, week_current)
    report  = delta or summary

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
                f"Research report for topic '{topic}':\n\n"
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