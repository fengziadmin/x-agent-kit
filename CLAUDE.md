# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

x-agent-kit is a Python framework for building autonomous AI agents with pluggable brains (LLM providers), tools, skills, and communication channels. Agents can run one-shot tasks or long-running daemons with cron scheduling and bidirectional messaging (Feishu/Lark).

## Build & Test Commands

```bash
# Install with all optional dependencies
pip install -e ".[all]"

# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_agent.py

# Run a specific test
pytest tests/test_agent.py::test_function_name -v
```

## Architecture

### Core Loop

`Agent` (x_agent_kit/agent.py) is the main orchestrator. `Agent.run(task)` sends a task to the brain, receives responses with optional tool calls, executes tools, and loops until the brain signals done or max_iterations is reached. `Agent.serve()` starts cron-scheduled execution and optionally a Feishu WebSocket listener for incoming messages.

### Pluggable Brains (`x_agent_kit/brain/`)

All brains implement `BaseBrain.think(messages, tools, system_prompt) -> BrainResponse`. Three implementations:
- **GeminiBrain** - Google Gemini via `google-genai` SDK
- **OpenAIBrain** - OpenAI GPT via `openai` SDK
- **ClaudeBrain** - Local Claude CLI with `--session-id`/`--resume` for stateful multi-turn without re-sending history

Brain selection is driven by `.agent/settings.json` `brain.provider` field. Provider credentials are resolved from environment variables via `api_key_env`.

### Tool System (`x_agent_kit/tools/`)

The `@tool(description)` decorator on any function auto-generates JSON schema from type annotations and docstring parameter descriptions. `ToolRegistry` manages registration and execution. Built-in tools (`builtin.py`) are factory functions that close over dependencies (memory, channels, plan manager) and return decorated callables.

### Channels (`x_agent_kit/channels/`)

`BaseChannel` defines the interface: `send_text()`, `send_card()`, `request_approval()`, `send_streaming_start()`. Implementations:
- **CLIChannel** - Terminal output
- **FeishuChannel** - Feishu/Lark with interactive cards, WebSocket message receive, streaming card updates, @mention detection, and emoji reactions

### Memory & Planning

- **Memory** (`memory.py`) - SQLite with FTS5 full-text search for persistent key-value storage
- **PlanManager** (`plan.py`) - SQLite-backed plan lifecycle: draft -> pending_approval -> executing -> completed, with per-step approval/rejection
- **ApprovalQueue** (`approval_queue.py`) - SQLite-backed async approval requests
- **ConversationManager** (`conversation.py`) - In-memory per-chat context for multi-turn dialogue

### Skills (`x_agent_kit/skills/`)

Markdown-based knowledge loaded on demand. Two formats: standalone `.agent/skills/name.md` or directory `.agent/skills/name/SKILL.md` with reference files. Skills are deduplicated during agent runs.

## Configuration

Agent reads `.agent/settings.json` with sections: `brain`, `providers`, `channels`, `skills`, `agent`, `memory`, `schedules`. See `tests/fixtures/.agent/settings.json` for a complete example.

Required environment variables depend on the configured provider:
- Gemini: `GOOGLE_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Feishu: `LARK_APP_ID`, `LARK_APP_SECRET`, `LARK_CHAT_ID`

## Key Patterns

- Brain implementations are lazily imported in `create_brain()` to avoid requiring all provider SDKs
- Built-in tools use factory functions (e.g., `create_save_memory_tool(memory)`) that return `@tool`-decorated closures
- The agent loop has special handling for `notify`, `request_approval`, and `load_skill` tool calls separate from regular tool execution
- Feishu streaming cards are updated progressively during the agent loop to show real-time progress
- `_reply_mode` flag suppresses streaming cards when replying to incoming messages in serve mode

## Python Version

Requires Python >= 3.11
