from __future__ import annotations
from typing import Any
from google import genai
from google.genai import types
from loguru import logger
from x_agent_kit.brain.base import BaseBrain
from x_agent_kit.models import BrainResponse, Message, ToolCall

class GeminiBrain(BaseBrain):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def think(self, messages: list[Message], tools: list[dict], system_prompt: str = "") -> BrainResponse:
        contents = self._build_contents(messages)
        gemini_tools = self._convert_tools(tools) if tools else None
        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt
        if gemini_tools:
            config.tools = gemini_tools
        response = self._client.models.generate_content(model=self._model, contents=contents, config=config)
        return self._parse_response(response)

    def _build_contents(self, messages: list[Message]) -> list[dict[str, Any]]:
        contents = []
        for msg in messages:
            if msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})
            elif msg.role == "tool_result":
                contents.append({"role": "user", "parts": [{"function_response": {"name": msg.tool_call_id or "unknown", "response": {"result": msg.content}}}]})
        return contents

    def _convert_tools(self, tools: list[dict]) -> list[types.Tool]:
        declarations = []
        for t in tools:
            func = t.get("function", {})
            declarations.append(types.FunctionDeclaration(name=func.get("name", ""), description=func.get("description", ""), parameters=func.get("parameters", {})))
        return [types.Tool(function_declarations=declarations)]

    def _parse_response(self, response) -> BrainResponse:
        if not response.candidates:
            return BrainResponse(text="")
        parts = response.candidates[0].content.parts
        text_parts = []
        tool_calls = []
        for part in parts:
            if part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args) if fc.args else {}))
            elif part.text:
                text_parts.append(part.text)
        return BrainResponse(text="".join(text_parts) if text_parts else None, tool_calls=tool_calls if tool_calls else None)
