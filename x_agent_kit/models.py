from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool_result"
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class BrainResponse:
    text: str | None = None
    tool_calls: list[ToolCall] | None = None
    done: bool = False
