# x-agent-kit Generic Framework Refactor — Design Spec

## Goal

Transform x-agent-kit from a framework with leaked business logic (Google Ads tool labels, hardcoded Chinese UI, special termination logic) into a truly generic, pip-installable agent framework that can serve multiple independent business agents.

## Context

- **x-agent-kit** — Python agent framework with pluggable brains, tools, skills, channels
- **x-google-ads-agent** — First consumer, currently coupled via `sys.path.insert` and hardcoded references in the framework
- Future agents (CRM, SEO, etc.) should be able to use x-agent-kit without any framework modifications

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target scope | Generic framework for multiple agents | Future-proof, clean separation |
| i18n approach | Full i18n system with locale files | Support zh_CN (default) and en |
| Tool label mechanism | `@tool(description, label=...)` parameter | Label defined by tool author, not framework |
| Default language | zh_CN | Primary user base is Chinese |
| Distribution | pip package (PyPI or private registry) | Replace sys.path hack |
| `memory_saved` termination | Replace with `stop_condition` callback | Framework should not assume business logic |

---

## 1. i18n System

### Structure

```
x_agent_kit/i18n/
├── __init__.py      # t(), set_locale(), get_locale(), load_extra_locale()
├── zh_CN.json       # Chinese (default)
└── en.json          # English
```

### API

```python
from x_agent_kit.i18n import t, set_locale, load_extra_locale

set_locale("en")                          # Switch language
t("agent.thinking")                       # → "Thinking..."
t("plan.pending_count", pending=3, total=5)  # → "3 pending / 5 total"
t("plan.type.quarterly", default="quarterly") # Fallback if key missing
```

### `t()` Function

```python
def t(key: str, default: str = "", **kwargs) -> str:
    text = _current_locale.get(key, default or key)
    if kwargs:
        text = text.format(**kwargs)
    return text
```

### Locale Keys (dot-path, grouped by module)

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

### Configuration

`settings.json` gains a `locale` field:

```json
{
  "locale": "zh_CN"
}
```

`Agent.__init__` calls `set_locale(config.locale)` on startup.

### Business-side Extension

Business agents can add their own keys without modifying the framework:

```python
from x_agent_kit.i18n import load_extra_locale
load_extra_locale("path/to/google_ads_zh_CN.json")
```

`load_extra_locale` merges keys into the current locale dict. Business keys take precedence over framework keys.

---

## 2. `@tool` Decorator — Label Support

### `ToolMeta` Extension

```python
@dataclass
class ToolMeta:
    name: str
    description: str
    func: Callable
    parameters: dict
    label: str = ""  # New: UI display label
```

### Decorator Change

```python
def tool(description: str, label: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        meta = ToolMeta(
            name=func.__name__,
            description=description,
            func=func,
            parameters=_extract_parameters(func),
            label=label,
        )
        func._tool_meta = meta
        return func
    return decorator
```

### `ToolRegistry.get_meta()`

```python
def get_meta(self, name: str) -> ToolMeta | None:
    tool = self._tools.get(name)
    return getattr(tool, '_tool_meta', None) if tool else None
```

### Framework Built-in Tool Labels

Built-in tools get generic labels (not business-specific). Labels are plain display strings, not i18n keys — they are set by the tool author via the `label` parameter. The emoji prefix makes them language-neutral enough for UI display.

| Tool | Label |
|------|-------|
| save_memory | 💾 Save Memory |
| recall_memories | 📝 Recall Memories |
| search_memory | 🔍 Search Memory |
| clear_memory | 🗑️ Clear Memory |
| load_skill | 📚 Load Skill |
| list_skills | 📋 List Skills |
| notify | 📢 Notify |
| request_approval | 📋 Request Approval |
| create_plan | 📝 Create Plan |
| submit_plan | 📤 Submit Plan |
| get_plan | 📄 Get Plan |
| execute_approved_steps | ▶️ Execute Steps |
| update_step | ✏️ Update Step |
| resubmit_step | 🔄 Resubmit Step |

Business agents set their own labels in their language of choice (e.g., `label="📊 查询广告数据"`).

---

## 3. Agent Run Loop Refactor

### ProgressRenderer

New file: `x_agent_kit/progress.py`

```python
class ProgressRenderer:
    """Encapsulates all streaming card / progress display logic."""

    def __init__(self, channel=None, enabled=True):
        self._card = None
        self._steps: list[str] = []
        if enabled and channel and hasattr(channel, "send_streaming_start"):
            self._card = channel.send_streaming_start(t("agent.thinking"))

    def add_step(self, label: str):
        """Add an in-progress step."""
        self._steps.append(f"{label}...")
        self._refresh()

    def complete_step(self, label: str):
        """Mark the last step as complete."""
        if self._steps:
            self._steps[-1] = f"✅ {label}"
        self._refresh()

    def update_text(self, text: str):
        """Update with arbitrary text (e.g., thinking indicator)."""
        if self._card:
            rendered = self._render_steps()
            self._card.update_text(rendered + "\n\n" + text if rendered else text)

    def finish(self, title: str, content: str, color: str = "green"):
        """Complete the streaming card."""
        if self._card:
            final = self._render_steps() + "\n---\n" + content if self._steps else content
            self._card.complete(title, final, color)

    def warn(self, title: str):
        """Close with warning state."""
        if self._card:
            self._card.complete(title, self._render_steps(), "yellow")

    def _render_steps(self) -> str:
        return "\n".join(f"- {s}" for s in self._steps)

    def _refresh(self):
        if self._card:
            self._card.update_text(self._render_steps())
```

### `stop_condition` Callback

```python
class Agent:
    def __init__(self, config_dir: str = ".agent", stop_condition=None):
        # ... existing init ...
        self._stop_condition = stop_condition  # Callable[[str, Any], bool] | None
```

### Run Loop Changes Summary

1. Delete `tool_labels` dict entirely
2. Delete `memory_saved` variable and its check
3. Replace inline streaming card logic with `ProgressRenderer`
4. Read tool label from `ToolMeta.label` via `self._tools.get_meta()`
5. All UI strings via `t()`
6. Check `stop_condition` after each tool execution

---

## 4. feishu_cards.py & feishu.py Cleanup

### feishu_cards.py

- Delete `_RISK_LABELS`, `_TYPE_LABELS`, `_PRIORITY_LABELS`, `_STEP_STATUS_LABELS` dicts
- Replace with `t()` calls: `t(f"plan.risk.{level}")`, `t(f"plan.type.{plan_type}")`
- Plan types become extensible: business agents add keys to their locale files
- All button text, status text, card titles via `t()`

### feishu.py

| Location | Current | After |
|----------|---------|-------|
| `_send_markdown_card` title | `"Agent Report"` | `t("card.agent_report")` |
| `request_approval` card title | `"审批: {action}"` | `t("card.approval_title", action=action)` |
| `_patch_card` approved text | hardcoded Chinese | `t("card.approval_approved", id=request_id[:8])` |
| `_patch_card` rejected text | hardcoded Chinese | `t("card.approval_rejected", id=request_id[:8])` |
| Execution success card | `"✅ 执行成功"` | `t("card.exec_success")` |
| Execution failure card | `"❌ 执行失败"` | `t("card.exec_failed")` |
| `send_streaming_start` default title | `"🤔 分析中..."` | `t("agent.thinking")` |

---

## 5. pip Package & Consumer Adaptation

### x-agent-kit pyproject.toml

```toml
[project]
version = "0.2.0"

[project.optional-dependencies]
feishu = ["lark-oapi>=1.5.0", "requests>=2.31.0"]
```

### x-google-ads-agent Changes

1. **`pyproject.toml`** — Add `x-agent-kit[gemini,feishu]>=0.2.0` to dependencies
2. **`agent_main.py`**:
   - Delete `sys.path.insert(0, "...")`
   - Add `label=` to each `@tool()` call
   - Pass `stop_condition=lambda name, _: name == "save_memory"` to `Agent()`
3. **Development**: `pip install -e ../x-agent-kit[gemini,feishu]`

---

## Files Changed (x-agent-kit)

| File | Action |
|------|--------|
| `x_agent_kit/i18n/__init__.py` | **New** — i18n core |
| `x_agent_kit/i18n/zh_CN.json` | **New** — Chinese locale |
| `x_agent_kit/i18n/en.json` | **New** — English locale |
| `x_agent_kit/progress.py` | **New** — ProgressRenderer |
| `x_agent_kit/tools/base.py` | **Edit** — `@tool` label param, `ToolMeta.label` |
| `x_agent_kit/tools/registry.py` | **Edit** — `get_meta()` method |
| `x_agent_kit/tools/builtin.py` | **Edit** — Add labels to built-in tools |
| `x_agent_kit/agent.py` | **Edit** — Major: delete tool_labels, delete memory_saved, add stop_condition, use ProgressRenderer, use t() |
| `x_agent_kit/config.py` | **Edit** — Add `locale` to Config |
| `x_agent_kit/channels/feishu.py` | **Edit** — All hardcoded text → t() |
| `x_agent_kit/channels/feishu_cards.py` | **Edit** — Delete label dicts, all text → t() |
| `pyproject.toml` | **Edit** — Version bump, feishu deps |

## Files Changed (x-google-ads-agent)

| File | Action |
|------|--------|
| `pyproject.toml` | **Edit** — Add x-agent-kit dependency |
| `agent_main.py` | **Edit** — Delete sys.path hack, add tool labels, add stop_condition |

## Not Changed

- Brain implementations (gemini, openai, claude) — no UI coupling
- Memory, PlanManager, ApprovalQueue, ConversationManager, Scheduler — pure logic
- Skills loader — no UI coupling
- Tests — will need updates after refactor but structure unchanged
