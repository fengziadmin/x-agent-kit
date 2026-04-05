from __future__ import annotations
import json
import openai
from loguru import logger
from x_agent_kit.brain.base import BaseBrain
from x_agent_kit.models import BrainResponse, Message, ToolCall

class OpenAIBrain(BaseBrain):
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def think(self, messages: list[Message], tools: list[dict], system_prompt: str = "") -> BrainResponse:
        oai_messages = self._build_messages(messages, system_prompt)
        kwargs = {"model": self._model, "messages": oai_messages}
        if tools:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    def _build_messages(self, messages: list[Message], system_prompt: str) -> list[dict]:
        oai = []
        if system_prompt:
            oai.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if msg.role == "tool_result":
                oai.append({"role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id or ""})
            else:
                oai.append({"role": msg.role, "content": msg.content})
        return oai

    def _parse_response(self, response) -> BrainResponse:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments)) for tc in msg.tool_calls]
        return BrainResponse(text=msg.content, tool_calls=tool_calls)
