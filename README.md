# x-agent-kit

Build autonomous AI agents with pluggable brains (LLM providers), tools, skills, and communication channels. Agents can run one-shot tasks or long-running daemons with cron scheduling and bidirectional messaging via Feishu/Lark.

## Install

```bash
# Core only
pip install x-agent-kit

# With specific providers
pip install x-agent-kit[gemini]
pip install x-agent-kit[openai]
pip install x-agent-kit[feishu]

# Everything
pip install x-agent-kit[all]
```

Requires Python >= 3.11.

## Quick Start

### 1. Create project structure

```
my-agent/
├── .agent/
│   ├── settings.json    # Agent configuration
│   ├── skills/          # Markdown knowledge files
│   └── memory/          # Auto-created, SQLite storage
└── main.py
```

### 2. Configure the agent

Create `.agent/settings.json`:

```json
{
  "brain": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "providers": {
    "gemini": {
      "type": "api",
      "api_key_env": "GOOGLE_API_KEY",
      "default_model": "gemini-2.5-flash"
    }
  },
  "channels": {
    "default": "cli"
  },
  "skills": {
    "paths": [".agent/skills"]
  },
  "agent": {
    "max_iterations": 50
  },
  "memory": {
    "enabled": true,
    "dir": ".agent/memory"
  },
  "locale": "zh_CN"
}
```

### 3. Write your agent

```python
from x_agent_kit import Agent, tool

@tool("Search the web for information", label="🔍 Search")
def search(query: str) -> str:
    """
    query: Keywords to search for
    """
    return f"Results for: {query}"

@tool("Save a note to file", label="📝 Save Note")
def save_note(filename: str, content: str) -> str:
    """
    filename: Name of the file to save
    content: Text content to write
    """
    with open(filename, "w") as f:
        f.write(content)
    return f"Saved to {filename}"

agent = Agent(config_dir=".agent")
agent.register_tools([search, save_note])
result = agent.run("Search for Python best practices and save a summary")
print(result)
```

## Architecture

```
User / Cron / Feishu Message
        │
        ▼
    ┌─────────┐
    │  Agent   │ ← orchestrator (think → tool_call → execute loop)
    └────┬────┘
         │
    ┌────┴─────────────────────┐
    │          │                │
    ▼          ▼                ▼
  Brain      Tools          Channel
 (LLM)    (functions)      (output)
    │          │                │
    ├─ Gemini  ├─ @tool defs   ├─ CLI
    ├─ OpenAI  ├─ Built-ins    └─ Feishu
    └─ Claude  │  (memory,
               │   skills,
               │   plans,
               │   approval)
               │
          ┌────┴────┐
          │         │
        Skills    Memory
       (.md)    (SQLite)
```

## Configuration Reference

Full `.agent/settings.json` example with all options:

```json
{
  "brain": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "providers": {
    "gemini": {
      "type": "api",
      "api_key_env": "GOOGLE_API_KEY",
      "default_model": "gemini-2.5-flash"
    },
    "openai": {
      "type": "api",
      "api_key_env": "OPENAI_API_KEY",
      "default_model": "gpt-4o"
    },
    "claude": {
      "type": "cli"
    }
  },
  "channels": {
    "default": "cli",
    "feishu": {
      "app_id_env": "LARK_APP_ID",
      "app_secret_env": "LARK_APP_SECRET",
      "default_chat_id_env": "LARK_CHAT_ID"
    }
  },
  "skills": {
    "paths": [".agent/skills"]
  },
  "agent": {
    "max_iterations": 50,
    "approval_timeout": 3600
  },
  "memory": {
    "enabled": true,
    "dir": ".agent/memory"
  },
  "locale": "zh_CN",
  "schedules": [
    {"cron": "0 9 * * *", "task": "Run daily analysis"},
    {"cron": "0 */6 * * *", "task": "Check for updates every 6 hours"}
  ]
}
```

### Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `brain.provider` | string | required | Provider name (must exist in `providers`) |
| `brain.model` | string | `""` | Model override (falls back to provider's `default_model`) |
| `providers.<name>.type` | string | required | `"api"` for SDK-based, `"cli"` for Claude CLI |
| `providers.<name>.api_key_env` | string | `""` | Environment variable containing the API key |
| `providers.<name>.default_model` | string | `""` | Default model for this provider |
| `channels.default` | string | `"cli"` | Default output channel |
| `channels.feishu` | object | — | Feishu channel config (see Feishu section) |
| `skills.paths` | list | `[".agent/skills"]` | Directories to search for skill files |
| `agent.max_iterations` | int | `50` | Max think-execute cycles per `run()` call |
| `agent.approval_timeout` | int | `3600` | Timeout (seconds) for approval requests |
| `memory.enabled` | bool | `true` | Enable persistent memory |
| `memory.dir` | string | `".agent/memory"` | Directory for SQLite databases |
| `locale` | string | `"zh_CN"` | UI language (`"zh_CN"` or `"en"`) |
| `schedules` | list | `[]` | Cron schedules for `serve()` mode |

### Environment Variables

Set these based on your configured providers:

```bash
# Gemini
export GOOGLE_API_KEY="your-key"

# OpenAI
export OPENAI_API_KEY="your-key"

# Feishu/Lark
export LARK_APP_ID="your-app-id"
export LARK_APP_SECRET="your-app-secret"
export LARK_CHAT_ID="your-chat-id"
```

## Brains (LLM Providers)

### Gemini

```json
{
  "brain": { "provider": "gemini", "model": "gemini-2.5-flash" },
  "providers": {
    "gemini": { "type": "api", "api_key_env": "GOOGLE_API_KEY" }
  }
}
```

Install: `pip install x-agent-kit[gemini]`

### OpenAI

```json
{
  "brain": { "provider": "openai", "model": "gpt-4o" },
  "providers": {
    "openai": { "type": "api", "api_key_env": "OPENAI_API_KEY" }
  }
}
```

Install: `pip install x-agent-kit[openai]`

### Claude (Local CLI)

Uses the Claude CLI with stateful sessions — no API key needed, no history re-sending.

```json
{
  "brain": { "provider": "claude" },
  "providers": {
    "claude": { "type": "cli" }
  }
}
```

Requires `claude` CLI installed and authenticated.

## Tools

### Creating Tools

Use the `@tool` decorator on any function. Parameter schemas are auto-generated from type annotations. Parameter descriptions are extracted from docstrings.

```python
from x_agent_kit import tool

@tool("Calculate compound interest", label="💰 Calculate Interest")
def compound_interest(principal: float, rate: float, years: int) -> str:
    """
    principal: Initial investment amount in dollars
    rate: Annual interest rate (e.g., 0.05 for 5%)
    years: Number of years to compound
    """
    result = principal * (1 + rate) ** years
    return f"${result:,.2f}"
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `description` | str | yes | Tool description sent to the LLM |
| `label` | str | no | Display label shown in streaming progress cards |

**Type mapping:**

| Python Type | JSON Schema Type |
|------------|-----------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `dict` | `"object"` |
| `list` | `"array"` |

Parameters without defaults are marked as `required`. Parameters with defaults include the default value in the schema.

### Registering Tools

```python
agent = Agent(config_dir=".agent")
agent.register_tools([compound_interest, search, save_note])
```

### Built-in Tools

When memory is enabled, the agent automatically registers these tools:

| Tool | Description |
|------|-------------|
| `save_memory` | Save key-value pairs to persistent SQLite storage |
| `recall_memories` | Recall recent memories from previous sessions |
| `search_memory` | Full-text search across all memories |
| `clear_memory` | Delete all stored memories |
| `load_skill` | Load a markdown skill file by name |
| `list_skills` | List all available skill names |
| `notify` | Send a message to the user via the configured channel |
| `request_approval` | Submit an action for human approval |
| `create_plan` | Create a structured multi-step execution plan |
| `submit_plan` | Send a plan for human approval via interactive card |
| `get_plan` | Retrieve plan status and step details |
| `execute_approved_steps` | Execute all approved steps in a plan |
| `update_step` | Modify a plan step after rejection/negotiation |
| `resubmit_step` | Resubmit a modified step for re-approval |

## Skills

Skills are markdown files that provide domain knowledge to the agent on demand. The LLM decides when to load them.

### Standalone Skill

Create `.agent/skills/my-topic.md`:

```markdown
# My Topic

Expert knowledge about this topic.

## Key Rules
- Rule 1: Always do X
- Rule 2: Never do Y

## Reference Data
| Metric | Target |
|--------|--------|
| CPA    | < $50  |
| ROAS   | > 3.0  |
```

### Directory Skill (with references)

For complex skills with multiple reference files:

```
.agent/skills/ad-optimization/
├── SKILL.md              # Main skill content
└── references/
    ├── bidding-guide.md   # Additional reference
    └── audience-tips.md   # Additional reference
```

All reference files are automatically concatenated when the skill is loaded.

### How Skills Work

1. Agent starts with `list_skills` and `load_skill` tools registered
2. LLM sees available skills and decides when domain knowledge is needed
3. LLM calls `load_skill(name="my-topic")` to inject the content
4. Duplicate loads within the same run are automatically skipped

## Memory

SQLite-backed persistent memory with FTS5 full-text search. Memories persist across agent runs.

```python
# The agent automatically uses memory tools:
# save_memory(key="analysis-2024-01", content="...")
# search_memory(query="campaign performance")
# recall_memories()  # recent entries

# Memory summary is prepended to each task automatically
```

### How It Works

- Stored in `{memory.dir}/memory.db` (SQLite with FTS5)
- Each entry has: `key`, `content`, `timestamp`
- `search_memory` uses full-text search with automatic fallback to LIKE queries
- `recall_memories` returns a formatted summary of recent entries
- Memory summary is automatically prepended to each `run()` call

## Plan System

The plan system enables structured, multi-step execution with human approval via interactive Feishu cards.

### Lifecycle

```
draft → pending_approval → partial_approved → executing → completed
                                  ↓
                              cancelled
```

### How It Works

1. LLM analyzes data and calls `create_plan()` with structured steps
2. Each step has: `action`, `tool_name`, `tool_args`, `priority`, `risk_level`
3. `submit_plan()` sends an interactive card to Feishu with per-step approve/reject buttons
4. Human reviews each step individually
5. Approved steps are auto-executed immediately
6. Rejected steps can be modified and resubmitted

### Plan Types

Plan types are customizable via locale files. Default types:

| Type | Label (zh_CN) | Label (en) |
|------|---------------|------------|
| `daily` | 日常计划 | Daily Plan |
| `weekly` | 周度策略 | Weekly Strategy |
| `monthly` | 月度复盘 | Monthly Review |

Business agents can add custom types by extending locale files.

## Channels

### CLI Channel

Terminal output with formatted cards and interactive approval prompts.

```json
{ "channels": { "default": "cli" } }
```

### Feishu/Lark Channel

Full integration with Feishu including:

- **Streaming cards** — Real-time progress updates during agent execution
- **Interactive approval cards** — Per-step approve/reject buttons for plans
- **@mention detection** — In group chats, only responds when @mentioned
- **Emoji reactions** — Shows "OnIt" while processing, "DONE" when complete
- **Markdown rendering** — Long responses rendered as rich cards
- **WebSocket** — Real-time bidirectional messaging

```json
{
  "channels": {
    "default": "feishu",
    "feishu": {
      "app_id_env": "LARK_APP_ID",
      "app_secret_env": "LARK_APP_SECRET",
      "default_chat_id_env": "LARK_CHAT_ID"
    }
  }
}
```

Install: `pip install x-agent-kit[feishu]`

## Running Modes

### One-shot Mode

Execute a single task and exit:

```python
agent = Agent(config_dir=".agent")
result = agent.run("Analyze today's performance data")
print(result)
```

### Serve Mode (Daemon)

Run as a long-lived process with cron scheduling and Feishu message handling:

```python
agent = Agent(config_dir=".agent")

# Starts cron jobs from config + Feishu WebSocket listener
agent.serve()

# Keep alive
import time
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print("Stopped.")
```

Schedules are configured in `settings.json`:

```json
{
  "schedules": [
    {"cron": "0 9 * * *", "task": "Run morning analysis and send report"},
    {"cron": "0 */6 * * *", "task": "Check metrics and alert if anomalies found"}
  ]
}
```

In serve mode, incoming Feishu messages trigger `agent.run()` with conversation context, enabling multi-turn dialogue.

## i18n (Internationalization)

The framework supports multiple languages. Default is Chinese (`zh_CN`), English (`en`) is also included.

### Switch Language

In `settings.json`:

```json
{ "locale": "en" }
```

### Extend with Custom Translations

Business agents can add their own translations without modifying the framework:

```python
from x_agent_kit.i18n import load_extra_locale

# Merge custom keys into current locale
load_extra_locale("path/to/my_translations.json")
```

Custom locale file example:

```json
{
  "plan.type.quarterly": "Quarterly Review",
  "plan.type.campaign_launch": "Campaign Launch Plan"
}
```

### Programmatic API

```python
from x_agent_kit.i18n import t, set_locale, get_locale

set_locale("en")
print(t("agent.thinking"))           # "🤔 Thinking..."
print(t("plan.pending_count",
        pending=3, total=5))         # "3 pending / 5 total"
print(t("custom.key",
        default="fallback"))         # "fallback" if key missing
```

## Custom Stop Conditions

By default, the agent loop runs until the brain signals `done` or `max_iterations` is reached. You can inject custom termination logic:

```python
# Stop after memory is saved (useful for analysis-then-save workflows)
agent = Agent(
    config_dir=".agent",
    stop_condition=lambda tool_name, result: tool_name == "save_memory"
)

# Stop after any approval is submitted
agent = Agent(
    config_dir=".agent",
    stop_condition=lambda tool_name, result: tool_name == "request_approval"
)
```

The callback receives `(tool_name: str, result: Any)` after each tool execution and returns `bool`.

## Complete Example

Here's a full example of a data analysis agent:

```python
import json
from x_agent_kit import Agent, tool

# Define domain-specific tools
@tool("Query sales data for a date range", label="📊 Query Sales")
def query_sales(start_date: str, end_date: str) -> str:
    """
    start_date: Start date in YYYY-MM-DD format
    end_date: End date in YYYY-MM-DD format
    """
    # Your data source here
    return json.dumps({"total": 15000, "orders": 342})

@tool("Generate a report from data", label="📄 Generate Report")
def generate_report(title: str, data: str) -> str:
    """
    title: Report title
    data: JSON data to include in the report
    """
    return f"Report '{title}' generated with {len(data)} chars of data"

# Create agent with custom stop condition
agent = Agent(
    config_dir=".agent",
    stop_condition=lambda name, _: name == "save_memory"
)
agent.register_tools([query_sales, generate_report])

# One-shot execution
result = agent.run("Analyze last week's sales and generate a summary report")
print(result)
```

## Development

```bash
# Clone the repo
git clone https://github.com/your-org/x-agent-kit.git
cd x-agent-kit

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a specific test file
pytest tests/test_agent.py -v

# Run a specific test
pytest tests/test_tools.py::TestToolLabel::test_tool_with_label -v
```

## License

MIT
