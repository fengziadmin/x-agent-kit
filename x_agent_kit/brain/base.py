from __future__ import annotations
from x_agent_kit.models import BrainResponse, Message

class BaseBrain:
    def think(self, messages: list[Message], tools: list[dict], system_prompt: str = "") -> BrainResponse:
        raise NotImplementedError
