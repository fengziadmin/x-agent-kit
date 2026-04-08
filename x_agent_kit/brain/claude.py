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
                "\n## OUTPUT FORMAT (STRICT JSON SCHEMA)\n\n"
                "You MUST respond with ONLY a valid JSON object matching one of these two schemas:\n\n"
                "Schema A — Call a tool:\n"
                '```json\n{"tool_calls": [{"name": "<tool_name>", "arguments": {"<param>": "<value>"}}]}\n```\n\n'
                "Schema B — Reply to user:\n"
                '```json\n{"text": "<your reply>", "done": true}\n```\n\n'
                "Schema C — Reply but continue (more tool calls needed):\n"
                '```json\n{"text": "<intermediate message>", "done": false}\n```\n\n'
                "RULES:\n"
                "- Output ONLY the JSON object. No markdown, no explanation, no prefix.\n"
                "- \"text\" must be a plain string, not nested JSON.\n"
                "- \"tool_calls\" is an array of objects with \"name\" (string) and \"arguments\" (object).\n"
                "- \"done\" is a boolean: true = conversation turn complete, false = more steps needed.\n"
                "- NEVER output raw text without wrapping in {\"text\": \"...\"}."
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
            "\nRespond with ONLY valid JSON: "
            '{"tool_calls": [{"name": "...", "arguments": {...}}]} '
            'or {"text": "your reply", "done": true}. '
            "No other text outside the JSON."
        )

        return "\n".join(parts)

    def _parse_output(self, output: str) -> BrainResponse:
        """Parse claude CLI JSON output with schema validation."""
        if not output:
            return BrainResponse(text="")

        try:
            data = json.loads(output)

            # claude --output-format json wraps in {"type":"result","result":"..."}
            if isinstance(data, dict) and "result" in data:
                inner = data["result"]
                if isinstance(inner, str):
                    result = self._validate_and_parse(inner)
                    return result
                return BrainResponse(text=str(inner))

            # Direct JSON response
            return self._validate_and_parse(output)

        except json.JSONDecodeError:
            return self._extract_text_fallback(output)

    def _validate_and_parse(self, raw: str) -> BrainResponse:
        """Parse and validate against expected schema.

        Expected schemas:
          A: {"tool_calls": [{"name": str, "arguments": dict}]}
          B: {"text": str, "done": bool}
          C: {"text": str, "done": false}
        """
        # Step 1: Try JSON parse
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            # JSON parse failed — try to extract text field via regex
            return self._extract_text_fallback(raw)

        if not isinstance(data, dict):
            return BrainResponse(text=str(data))

        # Step 2: Schema A — tool_calls
        if "tool_calls" in data and isinstance(data["tool_calls"], list):
            tool_calls = []
            for i, tc in enumerate(data["tool_calls"]):
                if not isinstance(tc, dict) or "name" not in tc:
                    continue
                tool_calls.append(ToolCall(
                    id=tc.get("name", str(i)),
                    name=tc["name"],
                    arguments=tc.get("arguments", {}),
                ))
            if tool_calls:
                return BrainResponse(tool_calls=tool_calls, text=data.get("text"))

        # Step 3: Schema B/C — text response
        if "text" in data and isinstance(data["text"], str):
            return BrainResponse(
                text=data["text"],
                done=bool(data.get("done", True)),
            )

        # Step 4: Has text key but wrong type — coerce
        if "text" in data:
            return BrainResponse(text=str(data["text"]), done=True)

        # Step 5: Unknown schema — try to extract useful content
        # Maybe LLM returned {"answer": "..."} or similar
        for key in ("answer", "response", "content", "message", "reply"):
            if key in data and isinstance(data[key], str):
                logger.warning(f"Non-standard schema: found '{key}' instead of 'text'")
                return BrainResponse(text=data[key], done=True)

        # Step 6: Give up, return string representation
        logger.warning(f"Unrecognized response schema: {list(data.keys())}")
        return BrainResponse(text=str(raw), done=True)

    def _extract_text_fallback(self, raw: str) -> BrainResponse:
        """Last resort: extract text from malformed output."""
        if not isinstance(raw, str):
            return BrainResponse(text=str(raw))

        import re

        # Try to find {"text": "..."} pattern
        match = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if match:
            text = match.group(1)
            text = text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
            return BrainResponse(text=text, done=True)

        # Try to find {"tool_calls": [...]} pattern
        tc_match = re.search(r'\{"tool_calls"\s*:\s*\[.*?\]\}', raw, re.DOTALL)
        if tc_match:
            try:
                return self._validate_and_parse(tc_match.group())
            except Exception:
                pass

        # Nothing parseable — return as plain text (strip JSON wrapper if present)
        clean = raw.strip()
        if clean.startswith('{') and clean.endswith('}'):
            # Looks like broken JSON, don't show to user
            logger.warning(f"Unparseable JSON response ({len(clean)} chars)")
            return BrainResponse(text="抱歉，处理出现异常，请重试。", done=True)

        return BrainResponse(text=clean, done=True)

