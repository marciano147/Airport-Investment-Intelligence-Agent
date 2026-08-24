"""SQLite chat history store for Streamlit conversations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("data") / "chat_history.db"


def _resolve_db_path(db_path: str | Path | None) -> Path:
    """Resolve test-provided paths while keeping the app default simple."""
    return Path(db_path) if db_path is not None else DB_PATH


def init_store(db_path: str | Path | None = None) -> None:
    """Create conversation and message tables if they do not already exist."""
    path = _resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
            )
            """
        )


def list_conversations(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return recent sidebar conversations ordered by last activity."""
    path = _resolve_db_path(db_path)
    init_store(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT thread_id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT 25
            """
        ).fetchall()
    return [dict(row) for row in rows]


def load_messages(
    thread_id: str,
    db_path: str | Path | None = None,
) -> list[dict[str, str]]:
    """Load one conversation as Streamlit/LangGraph-compatible messages."""
    path = _resolve_db_path(db_path)
    init_store(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_conversation(thread_id: str, db_path: str | Path | None = None) -> None:
    """Delete one saved conversation and all of its messages."""
    path = _resolve_db_path(db_path)
    init_store(path)
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))


def save_message(
    thread_id: str,
    role: str,
    content: str,
    db_path: str | Path | None = None,
) -> None:
    """Persist a chat message and create/update its conversation metadata."""
    path = _resolve_db_path(db_path)
    init_store(path)
    now = _utc_now()
    with sqlite3.connect(path) as conn:
        existing = conn.execute(
            "SELECT thread_id FROM conversations WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO conversations (thread_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (thread_id, _title_from_message(content), now, now),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE thread_id = ?",
                (now, thread_id),
            )
        conn.execute(
            """
            INSERT INTO messages (thread_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, role, content, now),
        )


def export_messages_json(
    thread_id: str,
    db_path: str | Path | None = None,
) -> str:
    """Export a conversation for the sidebar download button."""
    return json.dumps(load_messages(thread_id, db_path), indent=2)


def _title_from_message(content: str) -> str:
    compact = " ".join(content.split())
    if not compact:
        return "Untitled conversation"
    return compact[:60]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
