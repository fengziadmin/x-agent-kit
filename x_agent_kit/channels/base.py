from __future__ import annotations
from typing import Any

class BaseChannel:
    def send_text(self, text: str) -> dict[str, Any]:
        raise NotImplementedError
    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
    def request_approval(self, action: str, details: str, timeout: int = 3600) -> str:
        raise NotImplementedError
