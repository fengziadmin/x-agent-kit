"""Plan management — structured execution plans with per-step approval."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class PlanStep:
    step_id: str
    action: str
    tool_name: str
    tool_args: dict
    priority: str  # "high" | "medium" | "low"
    risk_level: str  # "high" | "medium" | "low"
    status: str = "pending"  # "pending" | "approved" | "rejected" | "negotiating" | "executed" | "failed"
    rejection_note: str | None = None
    execution_result: str | None = None


@dataclass
class Plan:
    plan_id: str
    title: str
    summary: str
    plan_type: str  # "daily" | "weekly" | "monthly"
    steps: list[PlanStep]
    status: str = "draft"  # "draft" | "pending_approval" | "partial_approved" | "executing" | "completed" | "cancelled"
    created_at: str = ""
    resolved_at: str | None = None


class PlanManager:
    """SQLite-backed plan lifecycle manager."""

    def __init__(self, db_path: str = ".agent/memory/plans.db") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                plan_type TEXT NOT NULL,
                status TEXT DEFAULT 'draft',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS plan_steps (
                step_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                action TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_args TEXT NOT NULL,
                priority TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                rejection_note TEXT,
                execution_result TEXT,
                step_order INTEGER NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
            );
        """)
        self._conn.commit()

    def create(self, title: str, summary: str, plan_type: str, steps: list[dict]) -> Plan:
        plan_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT INTO plans (plan_id, title, summary, plan_type, status, created_at) VALUES (?, ?, ?, ?, 'draft', ?)",
            (plan_id, title, summary, plan_type, now),
        )
        plan_steps = []
        for i, s in enumerate(steps):
            step_id = str(uuid.uuid4())
            self._conn.execute(
                "INSERT INTO plan_steps (step_id, plan_id, action, tool_name, tool_args, priority, risk_level, status, step_order) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (step_id, plan_id, s["action"], s["tool_name"], json.dumps(s["tool_args"], ensure_ascii=False), s["priority"], s["risk_level"], i),
            )
            plan_steps.append(PlanStep(
                step_id=step_id, action=s["action"], tool_name=s["tool_name"],
                tool_args=s["tool_args"], priority=s["priority"], risk_level=s["risk_level"],
            ))
        self._conn.commit()
        logger.info(f"Plan created: {plan_id} ({title}) with {len(steps)} steps")
        return Plan(plan_id=plan_id, title=title, summary=summary, plan_type=plan_type, steps=plan_steps, created_at=now)

    def get(self, plan_id: str) -> Plan | None:
        row = self._conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not row:
            return None
        step_rows = self._conn.execute(
            "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY step_order", (plan_id,)
        ).fetchall()
        steps = [
            PlanStep(
                step_id=s["step_id"], action=s["action"], tool_name=s["tool_name"],
                tool_args=json.loads(s["tool_args"]), priority=s["priority"],
                risk_level=s["risk_level"], status=s["status"],
                rejection_note=s["rejection_note"], execution_result=s["execution_result"],
            )
            for s in step_rows
        ]
        return Plan(
            plan_id=row["plan_id"], title=row["title"], summary=row["summary"],
            plan_type=row["plan_type"], steps=steps, status=row["status"],
            created_at=row["created_at"], resolved_at=row["resolved_at"],
        )

    def list_plans(self, plan_type: str | None = None, status: str | None = None, limit: int = 20) -> list[Plan]:
        query = "SELECT plan_id FROM plans WHERE 1=1"
        params: list = []
        if plan_type:
            query += " AND plan_type = ?"
            params.append(plan_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [self.get(r["plan_id"]) for r in rows]

    def update_step_status(self, plan_id: str, step_id: str, status: str, note: str | None = None) -> None:
        if note:
            self._conn.execute(
                "UPDATE plan_steps SET status = ?, rejection_note = ? WHERE plan_id = ? AND step_id = ?",
                (status, note, plan_id, step_id),
            )
        else:
            self._conn.execute(
                "UPDATE plan_steps SET status = ? WHERE plan_id = ? AND step_id = ?",
                (status, plan_id, step_id),
            )
        self._conn.commit()

    def update_step_action(self, plan_id: str, step_id: str, action: str, tool_name: str, tool_args: dict) -> None:
        self._conn.execute(
            "UPDATE plan_steps SET action = ?, tool_name = ?, tool_args = ?, status = 'pending' WHERE plan_id = ? AND step_id = ?",
            (action, tool_name, json.dumps(tool_args, ensure_ascii=False), plan_id, step_id),
        )
        self._conn.commit()

    def set_step_result(self, plan_id: str, step_id: str, result: str) -> None:
        self._conn.execute(
            "UPDATE plan_steps SET execution_result = ?, status = 'executed' WHERE plan_id = ? AND step_id = ?",
            (result, plan_id, step_id),
        )
        self._conn.commit()

    def refresh_plan_status(self, plan_id: str) -> None:
        """Auto-compute plan status from step statuses."""
        steps = self._conn.execute(
            "SELECT status FROM plan_steps WHERE plan_id = ?", (plan_id,)
        ).fetchall()
        statuses = [s["status"] for s in steps]
        if all(s == "executed" for s in statuses):
            new_status = "completed"
        elif all(s in ("executed", "failed", "rejected") for s in statuses):
            new_status = "completed"
        elif any(s in ("approved", "executed") for s in statuses) and any(s in ("rejected", "pending") for s in statuses):
            new_status = "partial_approved"
        elif any(s == "executed" for s in statuses):
            new_status = "executing"
        else:
            current = self._conn.execute("SELECT status FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
            new_status = current["status"] if current else "draft"
        now = datetime.now().isoformat() if new_status == "completed" else None
        self._conn.execute(
            "UPDATE plans SET status = ?, resolved_at = ? WHERE plan_id = ?",
            (new_status, now, plan_id),
        )
        self._conn.commit()
