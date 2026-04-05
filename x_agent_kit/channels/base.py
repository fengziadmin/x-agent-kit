from __future__ import annotations
from typing import Any

class BaseChannel:
    def send_text(self, text: str) -> dict[str, Any]:
        raise NotImplementedError
    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
    def request_approval(self, action: str, details: str, timeout: int = 3600) -> str:
        raise NotImplementedError
    def send_approval_card(self, request_id: str, action: str, details: str) -> dict[str, Any]:
        """Send an approval card with approve/reject buttons."""
        raise NotImplementedError
    def send_streaming_start(self, title: str = "Processing...") -> Any:
        """Start a streaming card. Returns a card handle for updates."""
        return None
