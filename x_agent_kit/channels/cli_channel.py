from __future__ import annotations
import json
from typing import Any
from x_agent_kit.channels.base import BaseChannel

class CLIChannel(BaseChannel):
    def send_text(self, text: str) -> dict[str, Any]:
        print(f"\n[Agent] {text}")
        return {"ok": True}
    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        print(f"\n{'='*40}")
        print(json.dumps(card, indent=2, ensure_ascii=False) if isinstance(card, dict) else card)
        print(f"{'='*40}\n")
        return {"ok": True}
    def request_approval(self, action: str, details: str, timeout: int = 3600) -> str:
        print(f"\n{'='*40}")
        print(f"  APPROVAL REQUIRED")
        print(f"  Action: {action}")
        print(f"  Details: {details}")
        print(f"{'='*40}")
        answer = input("  Approve? (y/n): ").strip().lower()
        return "APPROVED" if answer in ("y", "yes") else "REJECTED"

    def send_approval_card(self, request_id: str, action: str, details: str) -> dict[str, Any]:
        print(f"\n{'='*40}")
        print(f"  APPROVAL REQUEST: {action}")
        print(f"  Details: {details}")
        print(f"  ID: {request_id}")
        print(f"{'='*40}")
        return {"ok": True, "request_id": request_id}

    def send_streaming_start(self, title: str = "Processing...") -> Any:
        print(f"\n[{title}]")
        return CLIStreamingCard()


class CLIStreamingCard:
    def update_text(self, text: str):
        print(f"\r{text[:80]}", end="", flush=True)

    def append_text(self, text: str):
        print(text, end="", flush=True)

    def complete(self, title: str, content: str, color: str = "green"):
        print(f"\n[{title}] {content[:200]}")
