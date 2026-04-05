"""Async approval queue — stores pending approvals and executes on button click."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class ApprovalQueue:
    """SQLite-backed pending approval queue."""

    def __init__(self, db_path: str = ".agent/memory/memory.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pending_approvals (
                request_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_args TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
        """)
        self._conn.commit()

    def add(self, request_id: str, action: str, details: str, tool_name: str, tool_args: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO pending_approvals (request_id, action, details, tool_name, tool_args, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (request_id, action, details, tool_name, json.dumps(tool_args, ensure_ascii=False), datetime.now().isoformat()),
        )
        self._conn.commit()
        logger.info(f"Approval queued: {request_id} → {tool_name}")

    def get(self, request_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM pending_approvals WHERE request_id = ?", (request_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def resolve(self, request_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE pending_approvals SET status = ?, resolved_at = ? WHERE request_id = ?",
            (status, datetime.now().isoformat(), request_id),
        )
        self._conn.commit()

    def pending_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as c FROM pending_approvals WHERE status = 'pending'").fetchone()
        return row["c"]
