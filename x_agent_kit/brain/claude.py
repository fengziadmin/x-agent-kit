from __future__ import annotations
import json
import subprocess
from loguru import logger
from x_agent_kit.brain.base import BaseBrain
from x_agent_kit.models import BrainResponse, Message, ToolCall

class ClaudeBrain(BaseBrain):
    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout

    def think(self, messages: list[Message], tools: list[dict], system_prompt: str = "") -> BrainResponse:
        prompt = self._build_prompt(messages, tools, system_prompt)
        try:
            result = subprocess.run(["claude", "-p", prompt, "--output-format", "text"], capture_output=True, text=True, timeout=self._timeout)
            if result.returncode != 0:
                return BrainResponse(text=f"Claude CLI error: {result.stderr}")
            return self._parse_output(result.stdout.strip())
        except FileNotFoundError:
            return BrainResponse(text="Claude CLI not found")
        except subprocess.TimeoutExpired:
            return BrainResponse(text="Claude CLI timeout")

    def _build_prompt(self, messages: list[Message], tools: list[dict], system_prompt: str) -> str:
        parts = []
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")
        if tools:
            tool_desc = json.dumps(tools, indent=2)
            parts.append(f"Available tools (respond with JSON tool_calls array to use them):\n{tool_desc}\nResponse format: {{\"text\": \"...\", \"tool_calls\": [{{\"name\": \"...\", \"arguments\": {{}}}}]}}\n")
        for msg in messages:
            parts.append(f"{msg.role}: {msg.content}")
        return "\n".join(parts)

    def _parse_output(self, output: str) -> BrainResponse:
        try:
            data = json.loads(output)
            tool_calls = None
            if data.get("tool_calls"):
                tool_calls = [ToolCall(id=tc.get("name", ""), name=tc["name"], arguments=tc.get("arguments", {})) for tc in data["tool_calls"]]
            return BrainResponse(text=data.get("text"), tool_calls=tool_calls)
        except (json.JSONDecodeError, KeyError):
            return BrainResponse(text=output)
