"""
database.py — shared SQLite persistence for Driftwatch.
"""

import sqlite3
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "driftwatch.db"

DEFAULT_USER_EMAIL = "default@driftwatch.local"
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trackers (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                query TEXT NOT NULL,
                frequency TEXT NOT NULL,
                report_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                signal_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_run TEXT,
                last_week TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()
    ensure_default_user()


def ensure_default_user(conn=None):
    close = False
    if conn is None:
        conn = connect()
        close = True

    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (id, email, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_USER_EMAIL, datetime.datetime.now().isoformat()),
    )
    if close:
        conn.commit()
        conn.close()


def get_default_user_id():
    ensure_default_user()
    return DEFAULT_USER_ID


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def create_user(user_id: str, email: str, password_hash: str | None = None):
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, datetime.datetime.now().isoformat()),
        )
        conn.commit()


def get_user_by_email(email: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row_to_dict(row)


def update_user_last_login(user_id: str):
    with connect() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), user_id),
        )
        conn.commit()


def create_tracker(tracker: dict):
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO trackers (id, user_id, topic, query, frequency, report_mode, status, signal_count, created_at, last_run, last_week) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tracker["id"],
                tracker["user_id"],
                tracker["topic"],
                tracker["query"],
                tracker["frequency"],
                tracker["report_mode"],
                tracker.get("status", "idle"),
                int(tracker.get("signal_count", 0) or 0),
                tracker["created_at"],
                tracker.get("last_run"),
                tracker.get("last_week"),
            ),
        )
        conn.commit()


def list_trackers(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trackers WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def get_tracker(tracker_id: str, user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM trackers WHERE id = ? AND user_id = ?",
            (tracker_id, user_id),
        ).fetchone()
        return row_to_dict(row)


def delete_tracker(tracker_id: str, user_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM trackers WHERE id = ? AND user_id = ?",
            (tracker_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def save_tracker(tracker: dict):
    with connect() as conn:
        conn.execute(
            """
            UPDATE trackers
            SET topic = ?,
                query = ?,
                frequency = ?,
                report_mode = ?,
                status = ?,
                signal_count = ?,
                last_run = ?,
                last_week = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                tracker["topic"],
                tracker["query"],
                tracker["frequency"],
                tracker["report_mode"],
                tracker["status"],
                int(tracker.get("signal_count", 0) or 0),
                tracker.get("last_run"),
                tracker.get("last_week"),
                tracker["id"],
                tracker["user_id"],
            ),
        )
        conn.commit()


def tracker_exists(tracker_id: str, user_id: str) -> bool:
    return get_tracker(tracker_id, user_id) is not None
