# x-agent-kit

Build autonomous AI agents with pluggable brains, tools, skills, and channels.

## Install

```bash
pip install x-agent-kit[all]
```

## Quick Start

```python
from x_agent_kit import Agent, tool

@tool("Search the web")
def search(query: str) -> str:
    return f"Results for: {query}"

agent = Agent()  # reads .agent/settings.json
agent.register_tools([search])
agent.run("Find information about Python agents")
```

## Configuration

Create `.agent/settings.json`:

```json
{
  "brain": { "provider": "gemini", "model": "gemini-2.5-flash" },
  "providers": {
    "gemini": { "type": "api", "api_key_env": "GOOGLE_API_KEY" }
  },
  "channels": { "default": "cli" },
  "skills": { "paths": [".agent/skills"] },
  "agent": { "max_iterations": 50 }
}
```

## Features

- **Pluggable Brains**: Gemini, OpenAI, Claude CLI
- **Tools**: Decorate any function with `@tool`
- **Skills**: On-demand markdown knowledge loading
- **Channels**: CLI, Feishu, Slack (coming soon)
- **Serve Mode**: Cron-based scheduling for long-running agents
