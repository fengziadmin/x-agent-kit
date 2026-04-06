"""Persistent memory with SQLite + FTS5 full-text search.

Stores memory entries in SQLite with full-text search index.
Retrieves relevant memories by keyword search instead of loading all.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class Memory:
    """SQLite-backed persistent memory with full-text search."""

    def __init__(self, memory_dir: str = ".agent/memory") -> None:
        self._dir = Path(memory_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._dir / "memory.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._migrate_json_files()

    def _init_db(self) -> None:
        """Create tables if not exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                key, content, tokenize='unicode61'
            );
        """)
        self._conn.commit()

    def _migrate_json_files(self) -> None:
        """Migrate existing JSON memory files to SQLite."""
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                key = data.get("key", f.stem)
                content = data.get("content", "")
                timestamp = data.get("timestamp", datetime.now().isoformat())
                # Insert if not exists
                existing = self._conn.execute(
                    "SELECT key FROM memories WHERE key = ?", (key,)
                ).fetchone()
                if not existing:
                    self._conn.execute(
                        "INSERT INTO memories (key, content, timestamp) VALUES (?, ?, ?)",
                        (key, content, timestamp),
                    )
                    self._conn.execute(
                        "INSERT INTO memories_fts (key, content) VALUES (?, ?)",
                        (key, content),
                    )
                    logger.debug(f"Migrated memory from JSON: {key}")
                f.unlink()  # Remove migrated JSON file
            except Exception as exc:
                logger.error(f"Failed to migrate {f}: {exc}")
        self._conn.commit()

    def save(self, key: str, content: str) -> None:
        """Save or update a memory entry."""
        timestamp = datetime.now().isoformat()
        existing = self._conn.execute(
            "SELECT key FROM memories WHERE key = ?", (key,)
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE memories SET content = ?, timestamp = ? WHERE key = ?",
                (content, timestamp, key),
            )
            self._conn.execute(
                "DELETE FROM memories_fts WHERE key = ?", (key,)
            )
        else:
            self._conn.execute(
                "INSERT INTO memories (key, content, timestamp) VALUES (?, ?, ?)",
                (key, content, timestamp),
            )
        self._conn.execute(
            "INSERT INTO memories_fts (key, content) VALUES (?, ?)",
            (key, content),
        )
        self._conn.commit()
        logger.debug(f"Memory saved: {key}")

    def load(self, key: str) -> str | None:
        """Load a specific memory entry by key."""
        row = self._conn.execute(
            "SELECT content FROM memories WHERE key = ?", (key,)
        ).fetchone()
        return row["content"] if row else None

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search memories by keyword using FTS5."""
        if not query.strip():
            return self.load_recent(limit)
        try:
            rows = self._conn.execute(
                """SELECT m.key, m.content, m.timestamp,
                          rank
                   FROM memories_fts f
                   JOIN memories m ON f.key = m.key
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [{"key": r["key"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
        except Exception:
            # Fallback to LIKE search if FTS query syntax is invalid
            rows = self._conn.execute(
                """SELECT key, content, timestamp FROM memories
                   WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
            return [{"key": r["key"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

    def load_recent(self, limit: int = 10) -> list[dict]:
        """Load most recent memory entries."""
        rows = self._conn.execute(
            "SELECT key, content, timestamp FROM memories ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"key": r["key"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

    def load_all(self) -> list[dict]:
        """Load all memory entries, sorted by timestamp descending."""
        rows = self._conn.execute(
            "SELECT key, content, timestamp FROM memories ORDER BY timestamp DESC"
        ).fetchall()
        return [{"key": r["key"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

    def summary(self, max_entries: int = 5) -> str:
        """Return a summary of recent memories for injection into prompts."""
        entries = self.load_recent(max_entries)
        if not entries:
            return "No previous memories."
        parts = ["## Previous Session Memories\n"]
        for e in entries:
            parts.append(f"**[{e['timestamp'][:16]}] {e['key']}**\n{e['content'][:500]}\n")
        return "\n".join(parts)

    def delete(self, key: str) -> None:
        """Delete a memory entry."""
        self._conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        self._conn.execute("DELETE FROM memories_fts WHERE key = ?", (key,))
        self._conn.commit()

    def clear(self) -> None:
        """Delete all memories."""
        self._conn.execute("DELETE FROM memories")
        self._conn.execute("DELETE FROM memories_fts")
        self._conn.commit()

    def count(self) -> int:
        """Return total number of memories."""
        row = self._conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()
        return row["c"]
