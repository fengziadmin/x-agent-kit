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
