"""Claude Brain — uses claude CLI with session resume and streaming.

Approach (inspired by OpenClaw):
- First call: start new session with --session-id, stream-json output
- Subsequent calls: --resume session, pipe new messages via stdin
- Supports multi-turn conversation without re-sending full history
- Uses local Claude auth (OAuth), no API key needed
"""
from __future__ import annotations

import json
import subprocess
import uuid
from typing import Any

from loguru import logger

from x_agent_kit.brain.base import BaseBrain
from x_agent_kit.models import BrainResponse, Message, ToolCall


class ClaudeBrain(BaseBrain):
    """Claude via CLI subprocess with session persistence."""

    def __init__(self, timeout: int = 300, model: str = "") -> None:
        self._timeout = timeout
        self._model = model
        self._session_id = str(uuid.uuid4())
        self._first_call = True

    def think(
        self,
        messages: list[Message],
        tools: list[dict],
        system_prompt: str = "",
    ) -> BrainResponse:
        if self._first_call:
            return self._first_think(messages, tools, system_prompt)
        else:
            return self._resume_think(messages, tools)

    def _first_think(
        self, messages: list[Message], tools: list[dict], system_prompt: str
    ) -> BrainResponse:
        """First call: start a new session."""
        prompt = self._build_prompt(messages, tools)

        cmd = [
            "claude", "-p",
            "--output-format", "json",
            "--session-id", self._session_id,
            "--permission-mode", "bypassPermissions",
        ]
        if self._model:
            cmd.extend(["--model", self._model])
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        cmd.append(prompt)

        result = self._run(cmd)
        self._first_call = False
        return result

    def _resume_think(
        self, messages: list[Message], tools: list[dict]
    ) -> BrainResponse:
        """Subsequent calls: resume existing session."""
        # Build only the new messages (tool results) as the prompt
        new_content = self._build_resume_prompt(messages, tools)

        cmd = [
            "claude", "-p",
            "--output-format", "json",
            "--resume", self._session_id,
            "--permission-mode", "bypassPermissions",
        ]
        cmd.append(new_content)

        return self._run(cmd)

    def _run(self, cmd: list[str]) -> BrainResponse:
        """Execute claude CLI and parse response."""
        logger.debug(f"Claude CLI call: session={self._session_id[:8]}...")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            if result.returncode != 0:
                stderr = result.stderr[:500] if result.stderr else ""
                logger.error(f"Claude CLI error: {stderr}")
                return BrainResponse(text=f"Claude CLI error: {stderr}")

            raw = result.stdout.strip()
            logger.debug(f"Claude CLI raw output ({len(raw)} chars): {raw[:300]}...")
            return self._parse_output(raw)

        except FileNotFoundError:
            logger.error("Claude CLI not found in PATH")
            return BrainResponse(text="Claude CLI not found")
        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLI timeout ({self._timeout}s)")
            return BrainResponse(text=f"Claude CLI timeout after {self._timeout}s")

    def _build_prompt(
        self, messages: list[Message], tools: list[dict]
    ) -> str:
        """Build the initial prompt with tool definitions."""
        parts = []

        if tools:
            # Compact tool descriptions (not full JSON schema)
            tool_list = []
            for t in tools:
                func = t.get("function", {})
                name = func.get("name", "")
                desc = func.get("description", "")
                params = func.get("parameters", {}).get("properties", {})
                param_str = ", ".join(
                    f"{k}: {v.get('type', 'string')}"
                    for k, v in params.items()
                )
                tool_list.append(f"- {name}({param_str}) — {desc}")

            parts.append("You have these tools available:\n" + "\n".join(tool_list))
            parts.append(
                "\nTo call a tool, respond with ONLY a JSON object like this:\n"
                '{"tool_calls": [{"name": "tool_name", "arguments": {"param": "value"}}]}\n'
                "To give a final answer, respond with:\n"
                '{"text": "your answer", "done": true}\n'
                "Always respond with valid JSON. No other text."
            )

        for msg in messages:
            if msg.role == "user":
                parts.append(f"\nUser: {msg.content}")
            elif msg.role == "tool_result":
                parts.append(f"\nTool result ({msg.tool_call_id}): {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"\nAssistant: {msg.content}")

        return "\n".join(parts)

    def _build_resume_prompt(
        self, messages: list[Message], tools: list[dict]
    ) -> str:
        """Build prompt for resume — only include recent tool results."""
        parts = []
        # Find the last assistant message and only include messages after it
        last_assistant_idx = -1
        for i, msg in enumerate(messages):
            if msg.role == "assistant":
                last_assistant_idx = i

        recent = messages[last_assistant_idx + 1:] if last_assistant_idx >= 0 else messages[-3:]

        for msg in recent:
            if msg.role == "tool_result":
                parts.append(f"Tool result ({msg.tool_call_id}): {msg.content}")
            elif msg.role == "user":
                parts.append(msg.content)

        if not parts:
            parts.append("Continue with the next step.")

        parts.append(
            "\nRespond with JSON: "
            '{"tool_calls": [...]} or {"text": "...", "done": true}'
        )

        return "\n".join(parts)

    def _parse_output(self, output: str) -> BrainResponse:
        """Parse claude CLI JSON output."""
        if not output:
            return BrainResponse(text="")

        try:
            data = json.loads(output)

            # claude --output-format json wraps in {"type":"result","result":"..."}
            if isinstance(data, dict) and "result" in data:
                inner = data["result"]
                if isinstance(inner, str):
                    # Try to parse the inner result as JSON (tool calls)
                    # Handle mixed text+JSON: "Some text\n\n{\"tool_calls\": [...]}"
                    result = self._parse_inner(inner)
                    if result.text and not result.tool_calls:
                        # Maybe JSON is embedded in text, try to extract it
                        extracted = self._extract_json_from_text(inner)
                        if extracted.tool_calls:
                            return extracted
                    return result
                return BrainResponse(text=str(inner))

            # Direct JSON response
            return self._parse_inner(output)

        except json.JSONDecodeError:
            # Try to extract JSON from mixed text
            return self._extract_json_from_text(output)

    def _parse_inner(self, text: str) -> BrainResponse:
        """Parse the inner content which may contain tool calls."""
        try:
            data = json.loads(text) if isinstance(text, str) else text
        except (json.JSONDecodeError, TypeError):
            return BrainResponse(text=str(text))

        if isinstance(data, dict):
            tool_calls = None
            if data.get("tool_calls"):
                tool_calls = [
                    ToolCall(
                        id=tc.get("name", str(i)),
                        name=tc["name"],
                        arguments=tc.get("arguments", {}),
                    )
                    for i, tc in enumerate(data["tool_calls"])
                ]
            return BrainResponse(
                text=data.get("text"),
                tool_calls=tool_calls,
                done=data.get("done", False),
            )

        return BrainResponse(text=str(data))

    def _extract_json_from_text(self, text: str) -> BrainResponse:
        """Try to find JSON in text that may have extra content."""
        import re
        # Find the start of a JSON object containing tool_calls
        idx = text.find('{"tool_calls"')
        if idx == -1:
            idx = text.find('{ "tool_calls"')
        if idx >= 0:
            # Extract from { to the end, try parsing progressively shorter substrings
            candidate = text[idx:]
            for end in range(len(candidate), 0, -1):
                try:
                    data = json.loads(candidate[:end])
                    return self._parse_inner(candidate[:end])
                except (json.JSONDecodeError, ValueError):
                    continue

        # Fallback: regex for any JSON with tool_calls
        match = re.search(r'\{.*"tool_calls".*\}', text, re.DOTALL)
        if match:
            try:
                return self._parse_inner(match.group())
            except Exception:
                pass

        match = re.search(r'\{[^{}]*"text"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return self._parse_inner(match.group())
            except Exception:
                pass

        return BrainResponse(text=text)
