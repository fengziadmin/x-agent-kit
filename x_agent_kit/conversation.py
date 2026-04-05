# x_agent_kit/conversation.py
"""In-memory conversation context manager for multi-turn dialogue."""
from __future__ import annotations
from collections import defaultdict


class ConversationManager:
    """Manages recent conversation turns per chat, for injecting into agent prompts."""

    def __init__(self, max_turns: int = 20) -> None:
        self._max_turns = max_turns
        self._history: dict[str, list[dict]] = defaultdict(list)

    def add_message(self, role: str, content: str, chat_id: str) -> None:
        self._history[chat_id].append({"role": role, "content": content})
        if len(self._history[chat_id]) > self._max_turns:
            self._history[chat_id] = self._history[chat_id][-self._max_turns:]

    def get_context(self, chat_id: str) -> list[dict]:
        return list(self._history.get(chat_id, []))

    def clear(self, chat_id: str) -> None:
        self._history.pop(chat_id, None)
