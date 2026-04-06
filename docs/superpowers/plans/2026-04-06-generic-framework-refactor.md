# Generic Framework Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform x-agent-kit into a generic, pip-installable agent framework by extracting business logic, adding i18n, and making tool labels configurable.

**Architecture:** Six independent layers of changes: (1) i18n module, (2) tool label extension, (3) config locale support, (4) ProgressRenderer extraction, (5) agent run loop refactor, (6) feishu channel/cards cleanup, (7) packaging and consumer adaptation. Each task builds on the prior one but produces a working, committable state.

**Tech Stack:** Python 3.11+, pytest, JSON locale files

**Spec:** `docs/superpowers/specs/2026-04-06-generic-framework-refactor-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `x_agent_kit/i18n/__init__.py` | i18n core: `t()`, `set_locale()`, `get_locale()`, `load_extra_locale()` |
| `x_agent_kit/i18n/zh_CN.json` | Chinese locale (default) |
| `x_agent_kit/i18n/en.json` | English locale |
| `x_agent_kit/progress.py` | `ProgressRenderer` — encapsulates streaming card progress logic |
| `tests/test_i18n.py` | Tests for i18n module |
| `tests/test_progress.py` | Tests for ProgressRenderer |

### Modified Files
| File | What Changes |
|------|-------------|
| `x_agent_kit/tools/base.py` | `ToolMeta.label` field, `tool()` gains `label` param |
| `x_agent_kit/tools/registry.py` | Add `get_meta()` method |
| `x_agent_kit/tools/builtin.py` | All `create_*_tool` factories add `label=` to `@tool` |
| `x_agent_kit/config.py` | `Config.locale` field, `load_config` reads `locale` |
| `x_agent_kit/agent.py` | Delete `tool_labels`/`memory_saved`, add `stop_condition`, use `ProgressRenderer`, use `t()` |
| `x_agent_kit/channels/feishu.py` | All hardcoded strings → `t()` |
| `x_agent_kit/channels/feishu_cards.py` | Delete label dicts, all strings → `t()` |
| `pyproject.toml` | Version bump 0.2.0, add `requests` to feishu deps |
| `tests/fixtures/.agent/settings.json` | Add `"locale": "zh_CN"` |
| `tests/test_tools.py` | Add tests for `label` param and `get_meta()` |
| `tests/test_config.py` | Add test for `locale` field |
| `tests/test_agent.py` | Update `_make_agent` for new config shape, add `stop_condition` test |
| `tests/test_feishu_cards.py` | Initialize i18n before card tests |
| `tests/test_plan_cards.py` | Initialize i18n before card tests |
| `tests/test_builtin_tools.py` | Verify built-in tools have labels |

---

### Task 1: i18n Module — Core

**Files:**
- Create: `x_agent_kit/i18n/__init__.py`
- Create: `x_agent_kit/i18n/zh_CN.json`
- Create: `x_agent_kit/i18n/en.json`
- Create: `tests/test_i18n.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_i18n.py`:

```python
import pytest


class TestI18nCore:
    def test_default_locale_is_zh_cn(self):
        from x_agent_kit.i18n import get_locale
        assert get_locale() == "zh_CN"

    def test_t_returns_chinese_by_default(self):
        from x_agent_kit.i18n import t
        result = t("agent.thinking")
        assert "分析" in result

    def test_t_with_interpolation(self):
        from x_agent_kit.i18n import t
        result = t("plan.pending_count", pending=3, total=5)
        assert "3" in result
        assert "5" in result

    def test_t_fallback_to_default(self):
        from x_agent_kit.i18n import t
        result = t("nonexistent.key", default="fallback_value")
        assert result == "fallback_value"

    def test_t_fallback_to_key_when_no_default(self):
        from x_agent_kit.i18n import t
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_set_locale_switches_to_english(self):
        from x_agent_kit.i18n import t, set_locale
        set_locale("en")
        result = t("agent.thinking")
        assert "Thinking" in result
        # Reset to default
        set_locale("zh_CN")

    def test_get_locale_reflects_change(self):
        from x_agent_kit.i18n import get_locale, set_locale
        set_locale("en")
        assert get_locale() == "en"
        set_locale("zh_CN")
        assert get_locale() == "zh_CN"

    def test_load_extra_locale_merges_keys(self):
        import json
        import tempfile
        from pathlib import Path
        from x_agent_kit.i18n import t, set_locale, load_extra_locale
        set_locale("zh_CN")
        extra = {"custom.greeting": "你好世界"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(extra, f)
            f.flush()
            load_extra_locale(f.name)
        assert t("custom.greeting") == "你好世界"
        # Framework keys still work
        assert "分析" in t("agent.thinking")
        set_locale("zh_CN")  # Reset clears extra keys

    def test_load_extra_locale_overrides_framework_keys(self):
        import json
        import tempfile
        from x_agent_kit.i18n import t, set_locale, load_extra_locale
        set_locale("zh_CN")
        extra = {"agent.thinking": "CUSTOM THINKING"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(extra, f)
            f.flush()
            load_extra_locale(f.name)
        assert t("agent.thinking") == "CUSTOM THINKING"
        set_locale("zh_CN")  # Reset

    def test_set_locale_invalid_falls_back_to_zh_cn(self):
        from x_agent_kit.i18n import t, set_locale
        set_locale("fr_FR")  # Not available
        # Should fall back to zh_CN
        assert "分析" in t("agent.thinking")
        set_locale("zh_CN")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'x_agent_kit.i18n'`

- [ ] **Step 3: Create the i18n package**

Create `x_agent_kit/i18n/__init__.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "zh_CN"
_current_locale_name: str = _DEFAULT_LOCALE
_current_locale: dict[str, str] = {}


def _load_locale_file(name: str) -> dict[str, str]:
    """Load a locale JSON file by name. Returns empty dict if not found."""
    path = _LOCALE_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def set_locale(name: str) -> None:
    """Switch the active locale. Falls back to zh_CN if not found."""
    global _current_locale_name, _current_locale
    data = _load_locale_file(name)
    if not data:
        data = _load_locale_file(_DEFAULT_LOCALE)
        _current_locale_name = _DEFAULT_LOCALE
    else:
        _current_locale_name = name
    _current_locale = data


def get_locale() -> str:
    """Return the name of the current locale."""
    return _current_locale_name


def load_extra_locale(path: str) -> None:
    """Merge extra keys into the current locale. Extra keys take precedence."""
    global _current_locale
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _current_locale.update(data)


def t(key: str, default: str = "", **kwargs) -> str:
    """Translate a key. Supports {name} interpolation via kwargs."""
    text = _current_locale.get(key, default or key)
    if kwargs:
        text = text.format(**kwargs)
    return text


# Auto-load default locale on import
set_locale(_DEFAULT_LOCALE)
```

- [ ] **Step 4: Create zh_CN.json**

Create `x_agent_kit/i18n/zh_CN.json`:

```json
{
  "agent.thinking": "🤔 Agent 分析中...",
  "agent.complete": "分析完成",
  "agent.complete_title": "✅ 分析完成",
  "agent.max_iterations": "⚠️ 达到最大迭代",

  "card.approve": "✅ 批准",
  "card.reject": "❌ 拒绝",
  "card.approved": "✅ 已批准",
  "card.rejected": "❌ 已拒绝",
  "card.pending": "待审批",
  "card.approval_title": "⚠️ 审批: {action}",
  "card.approval_approved": "审批 `{id}` 已批准，正在执行...",
  "card.approval_rejected": "审批 `{id}` 已拒绝，操作已取消。",
  "card.agent_report": "Agent Report",
  "card.exec_success": "✅ 执行成功",
  "card.exec_failed": "❌ 执行失败",
  "card.operation": "操作",
  "card.result": "结果",
  "card.error": "错误",
  "card.preview": "预览",
  "card.continue_discuss": "💬 继续讨论",
  "card.rejection_reason": "拒绝原因",
  "card.new_proposal": "新方案",
  "card.negotiation_title": "🔄 协商: {action}",

  "plan.type.daily": "日常计划",
  "plan.type.weekly": "周度策略",
  "plan.type.monthly": "月度复盘",
  "plan.risk.high": "🔴 高风险",
  "plan.risk.medium": "🟡 中风险",
  "plan.risk.low": "🟢 低风险",
  "plan.priority.high": "紧急",
  "plan.priority.medium": "常规",
  "plan.priority.low": "低优",
  "plan.all_approved": "全部通过 ✅",
  "plan.pending_count": "{pending} 项待审批 / 共 {total} 项",
  "plan.summary": "摘要",
  "plan.processed": "已处理",
  "plan.step.approved": "✅ 已批准",
  "plan.step.rejected": "❌ 已拒绝",
  "plan.step.executed": "✅ 已执行",
  "plan.step.failed": "❌ 执行失败",
  "plan.step.negotiating": "💬 协商中",
  "plan.exec_success": "执行成功",
  "plan.exec_failed": "执行失败",

  "status.pending": "待处理",
  "status.processing": "处理中",
  "status.complete": "已完成",
  "status.error": "失败",
  "status.expired": "已过期"
}
```

- [ ] **Step 5: Create en.json**

Create `x_agent_kit/i18n/en.json`:

```json
{
  "agent.thinking": "🤔 Thinking...",
  "agent.complete": "Complete",
  "agent.complete_title": "✅ Complete",
  "agent.max_iterations": "⚠️ Max iterations reached",

  "card.approve": "✅ Approve",
  "card.reject": "❌ Reject",
  "card.approved": "✅ Approved",
  "card.rejected": "❌ Rejected",
  "card.pending": "Pending",
  "card.approval_title": "⚠️ Approval: {action}",
  "card.approval_approved": "Request `{id}` approved, executing...",
  "card.approval_rejected": "Request `{id}` rejected, action cancelled.",
  "card.agent_report": "Agent Report",
  "card.exec_success": "✅ Execution Success",
  "card.exec_failed": "❌ Execution Failed",
  "card.operation": "Operation",
  "card.result": "Result",
  "card.error": "Error",
  "card.preview": "Preview",
  "card.continue_discuss": "💬 Continue Discussion",
  "card.rejection_reason": "Rejection Reason",
  "card.new_proposal": "New Proposal",
  "card.negotiation_title": "🔄 Negotiate: {action}",

  "plan.type.daily": "Daily Plan",
  "plan.type.weekly": "Weekly Strategy",
  "plan.type.monthly": "Monthly Review",
  "plan.risk.high": "🔴 High Risk",
  "plan.risk.medium": "🟡 Medium Risk",
  "plan.risk.low": "🟢 Low Risk",
  "plan.priority.high": "Urgent",
  "plan.priority.medium": "Normal",
  "plan.priority.low": "Low",
  "plan.all_approved": "All Approved ✅",
  "plan.pending_count": "{pending} pending / {total} total",
  "plan.summary": "Summary",
  "plan.processed": "Processed",
  "plan.step.approved": "✅ Approved",
  "plan.step.rejected": "❌ Rejected",
  "plan.step.executed": "✅ Executed",
  "plan.step.failed": "❌ Failed",
  "plan.step.negotiating": "💬 Negotiating",
  "plan.exec_success": "Execution Success",
  "plan.exec_failed": "Execution Failed",

  "status.pending": "Pending",
  "status.processing": "Processing",
  "status.complete": "Complete",
  "status.error": "Error",
  "status.expired": "Expired"
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_i18n.py -v`
Expected: All 10 tests PASS

- [ ] **Step 7: Commit**

```bash
git add x_agent_kit/i18n/__init__.py x_agent_kit/i18n/zh_CN.json x_agent_kit/i18n/en.json tests/test_i18n.py
git commit -m "feat: add i18n module with zh_CN and en locales"
```

---

### Task 2: @tool Label Support & ToolRegistry.get_meta()

**Files:**
- Modify: `x_agent_kit/tools/base.py:10-54`
- Modify: `x_agent_kit/tools/registry.py:6-31`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tools.py`:

```python
class TestToolLabel:
    def test_tool_with_label(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff", label="📊 My Tool")
        def my_tool() -> str:
            return "ok"
        assert my_tool._tool_meta.label == "📊 My Tool"

    def test_tool_without_label_defaults_empty(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff")
        def my_tool() -> str:
            return "ok"
        assert my_tool._tool_meta.label == ""

    def test_label_not_in_schema(self):
        from x_agent_kit.tools.base import tool
        @tool("does stuff", label="📊 My Tool")
        def my_tool() -> str:
            return "ok"
        schema = my_tool._tool_meta.schema()
        assert "label" not in schema["function"]


class TestToolRegistryGetMeta:
    def test_get_meta_returns_tool_meta(self):
        from x_agent_kit.tools.base import tool
        from x_agent_kit.tools.registry import ToolRegistry
        @tool("adds", label="➕ Add")
        def add(a: int, b: int) -> int:
            return a + b
        reg = ToolRegistry()
        reg.register(add)
        meta = reg.get_meta("add")
        assert meta is not None
        assert meta.label == "➕ Add"
        assert meta.name == "add"

    def test_get_meta_returns_none_for_unknown(self):
        from x_agent_kit.tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert reg.get_meta("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools.py::TestToolLabel tests/test_tools.py::TestToolRegistryGetMeta -v`
Expected: FAIL — `TypeError: tool() got an unexpected keyword argument 'label'` and `AttributeError: 'ToolRegistry' object has no attribute 'get_meta'`

- [ ] **Step 3: Add `label` to ToolMeta and tool() decorator**

In `x_agent_kit/tools/base.py`, change the `ToolMeta` dataclass:

```python
@dataclass
class ToolMeta:
    name: str
    description: str
    func: Callable
    parameters: dict
    label: str = ""
```

Change the `tool()` function:

```python
def tool(description: str, label: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        meta = ToolMeta(name=func.__name__, description=description, func=func, parameters=_extract_parameters(func), label=label)
        func._tool_meta = meta
        return func
    return decorator
```

- [ ] **Step 4: Add `get_meta()` to ToolRegistry**

In `x_agent_kit/tools/registry.py`, add method to `ToolRegistry`:

```python
def get_meta(self, name: str) -> ToolMeta | None:
    return self._tools.get(name)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_tools.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add x_agent_kit/tools/base.py x_agent_kit/tools/registry.py tests/test_tools.py
git commit -m "feat: add label param to @tool decorator and get_meta() to ToolRegistry"
```

---

### Task 3: Add Labels to Built-in Tools

**Files:**
- Modify: `x_agent_kit/tools/builtin.py`
- Modify: `tests/test_builtin_tools.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_builtin_tools.py`:

```python
class TestBuiltinToolLabels:
    def test_save_memory_has_label(self):
        from x_agent_kit.tools.builtin import create_save_memory_tool
        from unittest.mock import MagicMock
        fn = create_save_memory_tool(MagicMock())
        assert fn._tool_meta.label != ""

    def test_load_skill_has_label(self):
        from x_agent_kit.tools.builtin import create_load_skill_tool
        from unittest.mock import MagicMock
        fn = create_load_skill_tool(MagicMock())
        assert fn._tool_meta.label != ""

    def test_notify_has_label(self):
        from x_agent_kit.tools.builtin import create_notify_tool
        fn = create_notify_tool({"default": MagicMock()})
        assert fn._tool_meta.label != ""

    def test_request_approval_has_label(self):
        from x_agent_kit.tools.builtin import create_request_approval_tool
        fn = create_request_approval_tool({"default": MagicMock()})
        assert fn._tool_meta.label != ""

    def test_create_plan_has_label(self):
        from x_agent_kit.tools.builtin import create_plan_tool
        from unittest.mock import MagicMock
        fn = create_plan_tool(MagicMock())
        assert fn._tool_meta.label != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_builtin_tools.py::TestBuiltinToolLabels -v`
Expected: FAIL — `AssertionError: assert '' != ''`

- [ ] **Step 3: Add labels to all built-in tool factories**

In `x_agent_kit/tools/builtin.py`, update each `@tool(...)` to include `label=`:

```python
@tool("Save important information to persistent memory for future sessions.", label="💾 Save Memory")
def save_memory(key: str, content: str) -> str:

@tool("Recall recent memories from previous sessions. Use search_memory for specific topics.", label="📝 Recall Memories")
def recall_memories() -> str:

@tool("Search past memories by keyword. Use this to find specific information from previous sessions.", label="🔍 Search Memory")
def search_memory(query: str, limit: int = 5) -> str:

@tool("Clear all persistent memories. Use with caution — this deletes all saved analysis records.", label="🗑️ Clear Memory")
def clear_memory() -> str:

@tool("Load a skill (domain knowledge) by name. Call this when you need specialized expertise.", label="📚 Load Skill")
def load_skill(name: str) -> str:

@tool("List all available skills. Call this to see what domain knowledge is available.", label="📋 List Skills")
def list_skills() -> str:

@tool("Send a notification message to the user.", label="📢 Notify")
def notify(message: str, channel: str = "default") -> bool:

@tool("Submit an action for human approval. Does NOT block — the action will be executed when approved.", label="📋 Request Approval")
def request_approval(action: str, details: str, tool_name: str = "", tool_args: str = "") -> str:

@tool("Create a structured execution plan from a list of steps. Returns the plan ID.", label="📝 Create Plan")
def create_plan(title: str, summary: str, plan_type: str, steps: str) -> str:

@tool("Submit a plan for human approval via Feishu. Sends an interactive approval card.", label="📤 Submit Plan")
def submit_plan(plan_id: str) -> str:

@tool("Get the current status of a plan and all its steps as JSON.", label="📄 Get Plan")
def get_plan(plan_id: str) -> str:

@tool("Execute all approved steps in a plan. Skips non-approved steps. Reports results via Feishu card.", label="▶️ Execute Steps")
def execute_approved_steps(plan_id: str) -> str:

@tool("Update a plan step's action, tool, or arguments after negotiation.", label="✏️ Update Step")
def update_step(plan_id: str, step_id: str, new_action: str, new_tool_name: str, new_tool_args: str = "{}") -> str:

@tool("Resubmit a rejected step for re-approval after modification. Sends a negotiation card.", label="🔄 Resubmit Step")
def resubmit_step(plan_id: str, step_id: str) -> str:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_builtin_tools.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add x_agent_kit/tools/builtin.py tests/test_builtin_tools.py
git commit -m "feat: add labels to all built-in tools"
```

---

### Task 4: Config Locale Support

**Files:**
- Modify: `x_agent_kit/config.py:52-97`
- Modify: `tests/fixtures/.agent/settings.json`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
    def test_loads_locale_config(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert config.locale == "zh_CN"

    def test_locale_defaults_to_zh_cn(self):
        from x_agent_kit.config import Config, BrainConfig, AgentConfig, SkillsConfig, MemoryConfig
        config = Config(
            brain=BrainConfig(provider="gemini"),
            providers={},
            channels={},
            skills=SkillsConfig(),
            agent=AgentConfig(),
        )
        assert config.locale == "zh_CN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::TestLoadConfig::test_loads_locale_config tests/test_config.py::TestLoadConfig::test_locale_defaults_to_zh_cn -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'locale'`

- [ ] **Step 3: Add locale to Config dataclass**

In `x_agent_kit/config.py`, add `locale` field to `Config`:

```python
@dataclass
class Config:
    brain: BrainConfig
    providers: dict[str, ProviderConfig]
    channels: dict[str, Any]
    skills: SkillsConfig
    agent: AgentConfig
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    schedules: list[ScheduleConfig] = field(default_factory=list)
    locale: str = "zh_CN"
```

In `load_config()`, read it from the JSON:

```python
    locale = raw.get("locale", "zh_CN")

    return Config(
        brain=brain,
        providers=providers,
        channels=channels,
        skills=skills,
        agent=agent,
        memory=memory,
        schedules=schedules,
        locale=locale,
    )
```

- [ ] **Step 4: Add locale to test fixture settings.json**

In `tests/fixtures/.agent/settings.json`, add `"locale": "zh_CN"` at the top level.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add x_agent_kit/config.py tests/fixtures/.agent/settings.json tests/test_config.py
git commit -m "feat: add locale field to Config"
```

---

### Task 5: ProgressRenderer

**Files:**
- Create: `x_agent_kit/progress.py`
- Create: `tests/test_progress.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_progress.py`:

```python
from unittest.mock import MagicMock


class TestProgressRenderer:
    def test_init_without_channel(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        assert renderer._card is None

    def test_init_with_channel_creates_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel, enabled=True)
        assert renderer._card is mock_card

    def test_init_disabled_skips_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        renderer = ProgressRenderer(channel=mock_channel, enabled=False)
        assert renderer._card is None
        mock_channel.send_streaming_start.assert_not_called()

    def test_add_step_appends_to_list(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.add_step("Loading data")
        assert len(renderer._steps) == 1
        assert "Loading data..." in renderer._steps[0]

    def test_complete_step_marks_done(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.add_step("Loading data")
        renderer.complete_step("Loading data")
        assert "✅" in renderer._steps[0]
        assert "Loading data" in renderer._steps[0]

    def test_add_step_updates_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.add_step("Step 1")
        mock_card.update_text.assert_called()

    def test_finish_calls_complete(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.finish("Done", "Final content", "green")
        mock_card.complete.assert_called_once_with("Done", "Final content", "green")

    def test_finish_with_steps_includes_progress(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.add_step("Step 1")
        renderer.complete_step("Step 1")
        renderer.finish("Done", "Final", "green")
        call_args = mock_card.complete.call_args[0]
        assert "Step 1" in call_args[1]
        assert "Final" in call_args[1]

    def test_warn_calls_complete_yellow(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.warn("Warning title")
        mock_card.complete.assert_called_once()
        assert mock_card.complete.call_args[0][2] == "yellow"

    def test_update_text_with_no_card_is_noop(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.update_text("something")  # Should not raise

    def test_finish_with_no_card_is_noop(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.finish("Done", "content")  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_progress.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'x_agent_kit.progress'`

- [ ] **Step 3: Implement ProgressRenderer**

Create `x_agent_kit/progress.py`:

```python
from __future__ import annotations

from typing import Any

from x_agent_kit.i18n import t


class ProgressRenderer:
    """Encapsulates all streaming card / progress display logic."""

    def __init__(self, channel: Any = None, enabled: bool = True) -> None:
        self._card: Any = None
        self._steps: list[str] = []
        if enabled and channel and hasattr(channel, "send_streaming_start"):
            self._card = channel.send_streaming_start(t("agent.thinking"))

    def add_step(self, label: str) -> None:
        """Add an in-progress step."""
        self._steps.append(f"{label}...")
        self._refresh()

    def complete_step(self, label: str) -> None:
        """Mark the last step as complete."""
        if self._steps:
            self._steps[-1] = f"✅ {label}"
        self._refresh()

    def update_text(self, text: str) -> None:
        """Update with arbitrary text (e.g., thinking indicator)."""
        if self._card:
            rendered = self._render_steps()
            self._card.update_text(rendered + "\n\n" + text if rendered else text)

    def finish(self, title: str, content: str, color: str = "green") -> None:
        """Complete the streaming card."""
        if self._card:
            final = self._render_steps() + "\n---\n" + content if self._steps else content
            self._card.complete(title, final, color)

    def warn(self, title: str) -> None:
        """Close with warning state."""
        if self._card:
            self._card.complete(title, self._render_steps(), "yellow")

    def _render_steps(self) -> str:
        return "\n".join(f"- {s}" for s in self._steps)

    def _refresh(self) -> None:
        if self._card:
            self._card.update_text(self._render_steps())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_progress.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add x_agent_kit/progress.py tests/test_progress.py
git commit -m "feat: add ProgressRenderer for streaming card progress display"
```

---

### Task 6: Refactor Agent Run Loop

**Files:**
- Modify: `x_agent_kit/agent.py`
- Modify: `tests/test_agent.py`

- [ ] **Step 1: Write the new/updated tests**

Replace and extend `tests/test_agent.py`:

```python
from unittest.mock import MagicMock, patch
from pathlib import Path
FIXTURES = Path(__file__).parent / "fixtures"


class TestAgentRun:
    def _make_agent(self, brain_responses, stop_condition=None):
        from x_agent_kit.agent import Agent
        mock_brain = MagicMock()
        mock_brain.think = MagicMock(side_effect=brain_responses)
        with patch("x_agent_kit.agent.load_config") as mock_config, \
             patch("x_agent_kit.agent.create_brain", return_value=mock_brain):
            mock_config.return_value = MagicMock(
                brain=MagicMock(provider="gemini"),
                providers={"gemini": MagicMock(type="api", resolve_api_key=lambda: "key")},
                channels={"default": "cli"},
                skills=MagicMock(paths=[str(FIXTURES / ".agent/skills")]),
                agent=MagicMock(max_iterations=50),
                memory=MagicMock(enabled=False),
                locale="zh_CN",
            )
            agent = Agent(config_dir=str(FIXTURES / ".agent"), stop_condition=stop_condition)
            return agent

    def test_run_returns_text_when_done(self):
        from x_agent_kit.models import BrainResponse
        agent = self._make_agent([BrainResponse(text="task complete", done=True)])
        assert agent.run("do something") == "task complete"

    def test_run_executes_tool_calls(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        from x_agent_kit.tools.base import tool
        @tool("adds numbers", label="➕ Add")
        def add(a: int, b: int) -> int:
            return a + b
        agent = self._make_agent([
            BrainResponse(tool_calls=[ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})]),
            BrainResponse(text="result is 5", done=True),
        ])
        agent.register_tools([add])
        assert "5" in agent.run("add 2+3")

    def test_run_stops_at_max_iterations(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        responses = [BrainResponse(tool_calls=[ToolCall(id="1", name="list_skills", arguments={})])] * 5
        agent = self._make_agent(responses)
        agent._config.agent.max_iterations = 3
        assert "max iterations" in agent.run("loop").lower()

    def test_run_text_without_tool_calls_completes(self):
        from x_agent_kit.models import BrainResponse
        agent = self._make_agent([BrainResponse(text="answer")])
        assert agent.run("question") == "answer"

    def test_stop_condition_terminates_loop(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        from x_agent_kit.tools.base import tool
        @tool("saves", label="💾 Save")
        def save_memory(key: str, content: str) -> str:
            return "saved"
        agent = self._make_agent(
            [
                BrainResponse(tool_calls=[ToolCall(id="1", name="save_memory", arguments={"key": "k", "content": "v"})]),
                BrainResponse(text="should not reach here", done=True),
            ],
            stop_condition=lambda name, _: name == "save_memory",
        )
        agent.register_tools([save_memory])
        result = agent.run("save something")
        # Should stop after save_memory, not reach the second brain response
        assert result != "should not reach here"

    def test_no_tool_labels_dict_in_agent(self):
        """Verify the hardcoded tool_labels dict has been removed."""
        import inspect
        from x_agent_kit import agent as agent_module
        source = inspect.getsource(agent_module)
        assert "query_campaigns" not in source
        assert "query_ga4_traffic" not in source
        assert "query_campaign_ga4" not in source
        assert "analyze_website" not in source

    def test_no_memory_saved_in_agent(self):
        """Verify the memory_saved early termination has been removed."""
        import inspect
        from x_agent_kit import agent as agent_module
        source = inspect.getsource(agent_module)
        assert "memory_saved" not in source
```

- [ ] **Step 2: Run tests to verify the new tests fail**

Run: `pytest tests/test_agent.py -v`
Expected: `test_stop_condition_terminates_loop` FAIL, `test_no_tool_labels_dict_in_agent` FAIL, `test_no_memory_saved_in_agent` FAIL. Existing tests may also break due to the new `locale` mock field — that's expected and will be fixed in step 3.

- [ ] **Step 3: Rewrite agent.py run loop**

Replace the full `Agent` class `__init__` signature and `run` method in `x_agent_kit/agent.py`. The complete new file:

```python
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
from loguru import logger
from x_agent_kit.config import Config, load_config
from x_agent_kit.i18n import t, set_locale
from x_agent_kit.models import BrainResponse, Message
from x_agent_kit.progress import ProgressRenderer
from x_agent_kit.skills.loader import SkillLoader
from x_agent_kit.tools.builtin import create_list_skills_tool, create_load_skill_tool, create_notify_tool, create_request_approval_tool, create_save_memory_tool, create_recall_memories_tool, create_search_memory_tool, create_clear_memory_tool, create_plan_tool, create_submit_plan_tool, create_get_plan_tool, create_execute_approved_steps_tool, create_update_step_tool, create_resubmit_step_tool
from x_agent_kit.tools.registry import ToolRegistry

def create_brain(config: Config):
    provider_name = config.brain.provider
    provider = config.providers.get(provider_name)
    if provider is None:
        raise ValueError(f"Provider '{provider_name}' not configured")
    model = config.brain.model or provider.default_model
    if provider.type == "api" and provider_name == "gemini":
        from x_agent_kit.brain.gemini import GeminiBrain
        return GeminiBrain(api_key=provider.resolve_api_key(), model=model)
    elif provider.type == "api" and provider_name == "openai":
        from x_agent_kit.brain.openai_brain import OpenAIBrain
        return OpenAIBrain(api_key=provider.resolve_api_key(), model=model)
    elif provider.type == "cli":
        from x_agent_kit.brain.claude import ClaudeBrain
        return ClaudeBrain()
    else:
        raise ValueError(f"Unknown provider type: {provider.type}")

def create_channels(config: Config) -> dict[str, Any]:
    channels = {}
    raw = config.channels
    default_name = raw.get("default", "cli") if isinstance(raw, dict) else "cli"
    from x_agent_kit.channels.cli_channel import CLIChannel
    channels["cli"] = CLIChannel()
    if isinstance(raw, dict) and "feishu" in raw and isinstance(raw["feishu"], dict):
        import os
        fc = raw["feishu"]
        app_id = os.environ.get(fc.get("app_id_env", ""), "")
        app_secret = os.environ.get(fc.get("app_secret_env", ""), "")
        chat_id = os.environ.get(fc.get("default_chat_id_env", ""), "")
        if app_id and app_secret and chat_id:
            from x_agent_kit.channels.feishu import FeishuChannel
            channels["feishu"] = FeishuChannel(app_id, app_secret, chat_id)
    channels["default"] = channels.get(default_name, channels["cli"])
    return channels

class Agent:
    def __init__(self, config_dir: str = ".agent", stop_condition: Callable[[str, Any], bool] | None = None) -> None:
        self._config = load_config(config_dir)
        set_locale(self._config.locale)
        self._brain = create_brain(self._config)
        self._tools = ToolRegistry()
        self._skills = SkillLoader(self._config.skills.paths)
        self._channels = create_channels(self._config)
        self._stop_condition = stop_condition
        self._tools.register(create_load_skill_tool(self._skills))
        self._tools.register(create_list_skills_tool(self._skills))
        self._tools.register(create_notify_tool(self._channels))

        self._memory = None
        self._approval_queue = None
        self._reply_mode = False
        if self._config.memory.enabled:
            from x_agent_kit.memory import Memory
            from x_agent_kit.approval_queue import ApprovalQueue
            self._memory = Memory(memory_dir=self._config.memory.dir)
            self._approval_queue = ApprovalQueue(db_path=str(Path(self._config.memory.dir) / "memory.db"))
            self._tools.register(create_save_memory_tool(self._memory))
            self._tools.register(create_recall_memories_tool(self._memory))
            self._tools.register(create_search_memory_tool(self._memory))
            self._tools.register(create_clear_memory_tool(self._memory))

            feishu = self._channels.get("feishu")
            if feishu and hasattr(feishu, 'set_approval_queue'):
                feishu.set_approval_queue(self._approval_queue)
                feishu.set_tool_executor(lambda name, args: self._tools.execute(name, args))

        self._tools.register(create_request_approval_tool(self._channels, self._approval_queue))

        self._plan_manager = None
        self._conversation = None
        if self._config.memory.enabled:
            from x_agent_kit.plan import PlanManager
            from x_agent_kit.conversation import ConversationManager
            plan_db = str(Path(self._config.memory.dir) / "plans.db") if self._config.memory.dir != ":memory:" else ":memory:"
            self._plan_manager = PlanManager(db_path=plan_db)
            self._conversation = ConversationManager()

            tool_executor = lambda name, args: self._tools.execute(name, args)
            self._tools.register(create_plan_tool(self._plan_manager))
            self._tools.register(create_submit_plan_tool(self._plan_manager, self._channels))
            self._tools.register(create_get_plan_tool(self._plan_manager))
            self._tools.register(create_execute_approved_steps_tool(self._plan_manager, tool_executor, self._channels))
            self._tools.register(create_update_step_tool(self._plan_manager))
            self._tools.register(create_resubmit_step_tool(self._plan_manager, self._channels))

            feishu = self._channels.get("feishu")
            if feishu and hasattr(feishu, 'set_plan_manager'):
                feishu.set_plan_manager(self._plan_manager)

    def register_tools(self, tools: list) -> None:
        for t in tools:
            self._tools.register(t)

    def run(self, task: str) -> str:
        if self._memory is not None:
            mem_summary = self._memory.summary()
            task_with_memory = f"{mem_summary}\n\n{task}"
        else:
            task_with_memory = task
        messages = [Message(role="user", content=task_with_memory)]
        max_iter = self._config.agent.max_iterations
        notified = False
        notify_content = ""
        loaded_skills = set()

        reply_mode = getattr(self, "_reply_mode", False)
        default_ch = self._channels.get("default")
        renderer = ProgressRenderer(channel=default_ch, enabled=not reply_mode)

        for i in range(max_iter):
            logger.info(f"Agent iteration {i+1}/{max_iter}")
            renderer.update_text(t("agent.thinking"))

            response = self._brain.think(messages=messages, tools=self._tools.schemas())
            if response.done or (response.text and not response.tool_calls):
                final = notify_content or response.text or t("agent.complete")
                renderer.finish(t("agent.complete_title"), final, "green")
                return notify_content or response.text or ""

            if response.tool_calls:
                for call in response.tool_calls:
                    if call.name == "notify":
                        if notified:
                            messages.append(Message(
                                role="tool_result", content="Already sent.",
                                tool_call_id=call.name,
                            ))
                            continue
                        notified = True
                        notify_content = call.arguments.get("message", "")
                        renderer.update_text(notify_content)
                        if not renderer._card:
                            self._tools.execute(call.name, call.arguments)
                        messages.append(Message(role="tool_result", content="OK", tool_call_id=call.name))
                        continue

                    if call.name == "request_approval":
                        meta = self._tools.get_meta(call.name)
                        label = meta.label if meta and meta.label else f"📋 {call.arguments.get('action', '')}"
                        renderer.add_step(label)
                        logger.info(f"Tool call: {call.name}({call.arguments})")
                        result = self._tools.execute(call.name, call.arguments)
                        renderer.complete_step(label)
                        messages.append(Message(role="tool_result", content=str(result), tool_call_id=call.name))
                        continue

                    if call.name == "load_skill":
                        skill_name = call.arguments.get("name", "")
                        if skill_name in loaded_skills:
                            logger.info(f"Skipping duplicate load_skill: {skill_name}")
                            messages.append(Message(
                                role="tool_result", content=f"Skill '{skill_name}' already loaded.",
                                tool_call_id=call.name,
                            ))
                            continue
                        loaded_skills.add(skill_name)

                    meta = self._tools.get_meta(call.name)
                    label = meta.label if meta and meta.label else f"🔧 {call.name}"
                    if call.name == "load_skill":
                        label = f"📚 {call.arguments.get('name', 'skill')}"
                    renderer.add_step(label)

                    logger.info(f"Tool call: {call.name}({call.arguments})")
                    result = self._tools.execute(call.name, call.arguments)
                    messages.append(Message(role="tool_result", content=str(result), tool_call_id=call.name))
                    renderer.complete_step(label)

                    if self._stop_condition and self._stop_condition(call.name, result):
                        logger.info(f"Stop condition met after {call.name}")
                        final = notify_content or t("agent.complete")
                        renderer.finish(t("agent.complete_title"), final, "green")
                        return response.text or ""

            if response.text:
                messages.append(Message(role="assistant", content=response.text))

        renderer.warn(t("agent.max_iterations"))
        return "Max iterations reached"

    def serve(self, schedules: list | None = None) -> None:
        """Start scheduled agent. If schedules not provided, reads from config."""
        feishu = self._channels.get("feishu")

        if self._conversation and feishu and hasattr(feishu, 'set_message_handler'):
            def on_message(chat_id: str, text: str, message_id: str = ""):
                logger.info(f"Incoming message from {chat_id}: {text[:50]}...")
                reaction_id = None
                if message_id and hasattr(feishu, 'add_reaction'):
                    reaction_id = feishu.add_reaction(message_id, "OnIt")
                self._conversation.add_message("user", text, chat_id)
                ctx = self._conversation.get_context(chat_id)
                context_str = "\n".join(f"[{m['role']}] {m['content']}" for m in ctx[:-1]) if len(ctx) > 1 else ""
                task = f"对话上下文:\n{context_str}\n\n用户消息: {text}" if context_str else text
                self._reply_mode = True
                try:
                    result = self.run(task)
                finally:
                    self._reply_mode = False
                self._conversation.add_message("assistant", result, chat_id)
                if message_id and hasattr(feishu, 'reply_text'):
                    feishu.reply_text(message_id, result)
                    if reaction_id:
                        feishu.remove_reaction(message_id, reaction_id)
                    feishu.add_reaction(message_id, "DONE")
                    logger.info(f"Replied to message {message_id[:20]}...")
            feishu.set_message_handler(on_message)
            logger.info("Feishu message handler registered for bidirectional comms")

        if feishu and hasattr(feishu, "_ensure_ws"):
            feishu._ensure_ws()
            logger.info("Feishu WebSocket started (card actions + message receive)")

        from x_agent_kit.scheduler import Scheduler
        sched = Scheduler()
        items = schedules or self._config.schedules
        for s in items:
            cron_expr = s.cron if hasattr(s, 'cron') else s['cron']
            task_str = s.task if hasattr(s, 'task') else s['task']
            logger.info(f"Schedule: {cron_expr} -> {task_str[:50]}...")
            sched.add(cron_expr, lambda t=task_str: self.run(t))
        sched.start()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agent.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: All existing tests PASS (some feishu_cards/plan_cards tests may need i18n init — see Task 8)

- [ ] **Step 6: Commit**

```bash
git add x_agent_kit/agent.py tests/test_agent.py
git commit -m "refactor: rewrite agent run loop — remove business logic, add stop_condition, use ProgressRenderer"
```

---

### Task 7: feishu.py — Replace Hardcoded Strings with t()

**Files:**
- Modify: `x_agent_kit/channels/feishu.py`

- [ ] **Step 1: Replace all hardcoded strings in feishu.py**

In `x_agent_kit/channels/feishu.py`, add the import at the top:

```python
from x_agent_kit.i18n import t
```

Then replace each hardcoded string:

1. `_send_markdown_card` (line 39): `title = "Agent Report"` → `title = t("card.agent_report")`

2. `request_approval` (line 85): `"审批: {action}"` → `t("card.approval_title", action=action)`

3. `request_approval` button texts (lines 89-90): `"Approve"` → `t("card.approve")`, `"Reject"` → `t("card.reject")`

4. `send_streaming_start` (line 107): default param `"🤔 分析中..."` → `t("agent.thinking")`

5. `_on_card_action` success card (line 343): `"✅ 执行成功"` → `t("card.exec_success")`

6. `_on_card_action` success card body (line 344): `f"**操作**: {p['action']}\n**结果**: {str(result)[:500]}"` → `f"**{t('card.operation')}**: {p['action']}\n**{t('card.result')}**: {str(result)[:500]}"`

7. `_on_card_action` failure card (line 350): `"❌ 执行失败"` → `t("card.exec_failed")`

8. `_on_card_action` failure card body (line 351): `f"**操作**: {p['action']}\n**错误**: {str(exc)[:500]}"` → `f"**{t('card.operation')}**: {p['action']}\n**{t('card.error')}**: {str(exc)[:500]}"`

9. `_patch_card` (lines 388-395): Replace:
```python
        if decision == "approve":
            title = t("card.approved")
            color = "green"
            content = t("card.approval_approved", id=request_id[:8])
        else:
            title = t("card.rejected")
            color = "red"
            content = t("card.approval_rejected", id=request_id[:8])
```

10. `request_approval` card body (line 87): `f"**操作**: {action}\n\n{details}"` → `f"**{t('card.operation')}**: {action}\n\n{details}"`

- [ ] **Step 2: Run the feishu channel tests**

Run: `pytest tests/test_channels.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add x_agent_kit/channels/feishu.py
git commit -m "refactor: replace all hardcoded strings in feishu.py with i18n t() calls"
```

---

### Task 8: feishu_cards.py — Replace Label Dicts with t()

**Files:**
- Modify: `x_agent_kit/channels/feishu_cards.py`
- Modify: `tests/test_feishu_cards.py`
- Modify: `tests/test_plan_cards.py`

- [ ] **Step 1: Update feishu_cards.py**

In `x_agent_kit/channels/feishu_cards.py`, add the import:

```python
from x_agent_kit.i18n import t
```

Delete these module-level dicts:
- `_RISK_LABELS`
- `_PRIORITY_LABELS`
- `_TYPE_LABELS`
- `_STEP_STATUS_LABELS`

In `build_status_card` (line 178), replace:
```python
    tag_text = {"pending": "待处理", "processing": "处理中", "complete": "已完成", "error": "失败", "expired": "已过期"}
```
with:
```python
    tag_text_key = f"status.{status}"
    tag_display = t(tag_text_key, default=status)
```
And replace `tag_text.get(status, status)` with `tag_display`.

In `build_confirmation_card` (lines 197-228), replace:
- `"**操作**: {action}"` → `f"**{t('card.operation')}**: {action}"`
- `"**预览**:"` → `f"**{t('card.preview')}**:"`
- Button text `"✅ 批准"` → `t("card.approve")`
- Button text `"❌ 拒绝"` → `t("card.reject")`
- Header title `f"⚠️ 审批: {action}"` → `t("card.approval_title", action=action)`
- Tag text `"待审批"` → `t("card.pending")`

In `build_plan_approval_card` (lines 249-325), replace:
- `_TYPE_LABELS.get(plan.plan_type, plan.plan_type)` → `t(f"plan.type.{plan.plan_type}", default=plan.plan_type)`
- `_RISK_LABELS.get(step.risk_level, step.risk_level)` → `t(f"plan.risk.{step.risk_level}", default=step.risk_level)`
- `_PRIORITY_LABELS.get(step.priority, step.priority)` → `t(f"plan.priority.{step.priority}", default=step.priority)`
- `_STEP_STATUS_LABELS[step.status]` → `t(f"plan.step.{step.status}", default=step.status)`
- Button text `"✅ 批准"` → `t("card.approve")`
- Button text `"❌ 拒绝"` → `t("card.reject")`
- `f"**摘要**: {plan.summary}"` → `f"**{t('plan.summary')}**: {plan.summary}"`
- `f"全部通过 ✅"` → `t("plan.all_approved")`
- The pending count string → `t("plan.pending_count", pending=pending, total=step_count)`
- `"已处理"` → `t("plan.processed")`

In `build_step_result_card` (lines 328-346), replace:
- `"执行失败"` → `t("plan.exec_failed")`
- `"执行成功"` → `t("plan.exec_success")`
- `"**操作**: {step.action}"` → `f"**{t('card.operation')}**: {step.action}"`
- `"**结果**: {result}"` → `f"**{t('card.result')}**: {result}"`

In `build_negotiation_card` (lines 349-384), replace:
- `f"**拒绝原因**: {step.rejection_note}"` → `f"**{t('card.rejection_reason')}**: {step.rejection_note}"`
- `f"**新方案**: {new_proposal}"` → `f"**{t('card.new_proposal')}**: {new_proposal}"`
- Button `"✅ 批准"` → `t("card.approve")`
- Button `"💬 继续讨论"` → `t("card.continue_discuss")`
- Header `f"🔄 协商: {step.action}"` → `t("card.negotiation_title", action=step.action)`

In `StreamingCard.start` (line 41): `"正在思考..."` → `t("agent.thinking")`

- [ ] **Step 2: Add i18n initialization to test files**

In `tests/test_feishu_cards.py`, add at the top before class definitions:

```python
from x_agent_kit.i18n import set_locale
set_locale("zh_CN")
```

In `tests/test_plan_cards.py`, add at the top before class definitions:

```python
from x_agent_kit.i18n import set_locale
set_locale("zh_CN")
```

- [ ] **Step 3: Run card tests**

Run: `pytest tests/test_feishu_cards.py tests/test_plan_cards.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add x_agent_kit/channels/feishu_cards.py tests/test_feishu_cards.py tests/test_plan_cards.py
git commit -m "refactor: replace hardcoded label dicts in feishu_cards.py with i18n t() calls"
```

---

### Task 9: Package Version Bump & Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

In `pyproject.toml`:

Change version:
```toml
version = "0.2.0"
```

Update feishu optional dependencies:
```toml
feishu = ["lark-oapi>=1.5.0", "requests>=2.31.0"]
```

- [ ] **Step 2: Verify install still works**

Run: `pip install -e ".[dev]"`
Expected: Install succeeds

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.2.0, add requests to feishu deps"
```

---

### Task 10: Full Test Suite Verification

**Files:** None new — run all existing tests.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: If any failures, fix them**

Common issues:
- Tests that import `feishu_cards` functions without i18n initialized — add `set_locale("zh_CN")` at module level
- Tests that mock Agent config without `locale` field — add `locale="zh_CN"` to mock
- Tests that check for exact Chinese strings — should still work since default locale is zh_CN

- [ ] **Step 3: Commit any test fixes**

```bash
git add tests/
git commit -m "fix: update tests for i18n and refactored agent"
```

---

### Task 11: Adapt x-google-ads-agent

**Files:**
- Modify: `/Users/rayeyemacmini2018/Desktop/Github/x-google-ads-agent/pyproject.toml`
- Modify: `/Users/rayeyemacmini2018/Desktop/Github/x-google-ads-agent/agent_main.py`

- [ ] **Step 1: Update pyproject.toml**

Add `x-agent-kit` to dependencies:

```toml
dependencies = [
    "x-agent-kit[gemini,feishu]>=0.2.0",
    # ... rest unchanged
]
```

- [ ] **Step 2: Update agent_main.py — remove sys.path hack**

Delete line 3:
```python
sys.path.insert(0, "/Users/rayeyemacmini2018/Desktop/Github/x-agent-kit")
```

- [ ] **Step 3: Add labels to all @tool decorators**

```python
@tool("Query all enabled campaigns with performance metrics for the last N days", label="📊 查询广告数据")
def query_campaigns(days: int = 7) -> str:

@tool("Query ad group performance for the last N days", label="📊 查询广告组")
def query_ad_groups(days: int = 7) -> str:

@tool("Query keyword performance for the last N days", label="📊 查询关键词")
def query_keywords(days: int = 7) -> str:

@tool("Query ad creative performance for the last N days", label="📊 查询广告创意")
def query_ads(days: int = 7) -> str:

@tool("Query search terms report for the last N days", label="📊 查询搜索词")
def query_search_terms(days: int = 7) -> str:

@tool("Query audience performance for the last N days", label="📊 查询受众")
def query_audiences(days: int = 7) -> str:

@tool("Query GA4 traffic summary for the last N days", label="📈 查询 GA4 流量")
def query_ga4_traffic(days: int = 7) -> str:

@tool("Update a campaign's daily budget. Requires approval.", label="💰 修改预算")
def update_budget(campaign_resource: str, budget_dollars: float) -> str:

@tool("Update a campaign's bidding strategy. Requires approval.", label="🎯 修改出价策略")
def update_bidding_strategy(campaign_resource: str, strategy: str, target_cpa_micros: int = 0, target_roas: float = 0.0) -> str:

@tool("Pause a keyword. Requires approval.", label="⏸️ 暂停关键词")
def pause_keyword(criterion_resource: str) -> str:

@tool("Pause an ad. Requires approval.", label="⏸️ 暂停广告")
def pause_ad(ad_group_ad_resource: str) -> str:

@tool("Pause a campaign. Requires approval.", label="⏸️ 暂停广告系列")
def pause_campaign(campaign_resource: str) -> str:

@tool("Add keywords to an ad group. Requires approval.", label="➕ 添加关键词")
def add_campaign_keywords(ad_group_resource: str, keywords: list, match_type: str = "BROAD") -> str:

@tool("Add negative keywords to a campaign. Requires approval.", label="🚫 添加否定关键词")
def add_negative_kw(campaign_resource: str, keywords: list) -> str:

@tool("Create a new RSA ad in an existing ad group. Requires approval.", label="✍️ 创建广告")
def create_rsa_ad(ad_group_resource: str, headlines: list, descriptions: list, final_url: str) -> str:

@tool("Analyze a website URL and extract title, description, keywords, main content", label="🌐 分析网站内容")
def analyze_website(url: str) -> str:
```

- [ ] **Step 4: Add stop_condition to Agent init**

Change:
```python
agent = Agent(config_dir=".agent")
```
to:
```python
agent = Agent(config_dir=".agent", stop_condition=lambda name, _: name == "save_memory")
```

- [ ] **Step 5: Install x-agent-kit locally and verify**

Run: `cd /Users/rayeyemacmini2018/Desktop/Github/x-google-ads-agent && pip install -e "../x-agent-kit[gemini,feishu]"`
Expected: Install succeeds

- [ ] **Step 6: Verify import works**

Run: `cd /Users/rayeyemacmini2018/Desktop/Github/x-google-ads-agent && python -c "from x_agent_kit import Agent, tool; print('OK')"`
Expected: Prints `OK`

- [ ] **Step 7: Commit**

```bash
cd /Users/rayeyemacmini2018/Desktop/Github/x-google-ads-agent
git add pyproject.toml agent_main.py
git commit -m "refactor: use x-agent-kit as pip dependency, add tool labels, add stop_condition"
```
