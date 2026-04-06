from __future__ import annotations
from pathlib import Path
from typing import Any
from loguru import logger
from x_agent_kit.config import Config, load_config
from x_agent_kit.models import BrainResponse, Message
from x_agent_kit.skills.loader import SkillLoader
from x_agent_kit.tools.builtin import create_list_skills_tool, create_load_skill_tool, create_notify_tool, create_request_approval_tool, create_save_memory_tool, create_recall_memories_tool, create_search_memory_tool, create_plan_tool, create_submit_plan_tool, create_get_plan_tool, create_execute_approved_steps_tool, create_update_step_tool, create_resubmit_step_tool
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
    def __init__(self, config_dir: str = ".agent") -> None:
        self._config = load_config(config_dir)
        self._brain = create_brain(self._config)
        self._tools = ToolRegistry()
        self._skills = SkillLoader(self._config.skills.paths)
        self._channels = create_channels(self._config)
        self._tools.register(create_load_skill_tool(self._skills))
        self._tools.register(create_list_skills_tool(self._skills))
        self._tools.register(create_notify_tool(self._channels))

        self._memory = None
        self._approval_queue = None
        if self._config.memory.enabled:
            from x_agent_kit.memory import Memory
            from x_agent_kit.approval_queue import ApprovalQueue
            self._memory = Memory(memory_dir=self._config.memory.dir)
            self._approval_queue = ApprovalQueue(db_path=str(Path(self._config.memory.dir) / "memory.db"))
            self._tools.register(create_save_memory_tool(self._memory))
            self._tools.register(create_recall_memories_tool(self._memory))
            self._tools.register(create_search_memory_tool(self._memory))

            # Wire up feishu channel for async execution (WebSocket started in serve() only)
            feishu = self._channels.get("feishu")
            if feishu and hasattr(feishu, 'set_approval_queue'):
                feishu.set_approval_queue(self._approval_queue)
                feishu.set_tool_executor(lambda name, args: self._tools.execute(name, args))

        self._tools.register(create_request_approval_tool(self._channels, self._approval_queue))

        # Plan manager (requires memory enabled)
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
        memory_saved = False

        # Start streaming card if feishu channel available
        streaming_card = None
        default_ch = self._channels.get("default")
        if default_ch and hasattr(default_ch, "send_streaming_start"):
            streaming_card = default_ch.send_streaming_start("🤔 Agent 分析中...")
        notify_content = ""
        progress_steps = []  # Human-readable progress
        loaded_skills = set()  # Track loaded skills to prevent duplicates

        # Tool name → readable label
        tool_labels = {
            "recall_memories": "📝 回顾历史记忆",
            "query_campaigns": "📊 查询广告数据",
            "query_ga4_traffic": "📈 查询 GA4 流量",
            "query_campaign_ga4": "📈 查询广告系列 GA4 数据",
            "load_skill": "📚 加载专业知识",
            "search_memory": "🔍 搜索历史记忆",
            "analyze_website": "🌐 分析网站内容",
            "save_memory": "💾 保存分析记录",
        }

        def _render_progress() -> str:
            return "\n".join(f"- {s}" for s in progress_steps)

        for i in range(max_iter):
            logger.info(f"Agent iteration {i+1}/{max_iter}")

            if streaming_card:
                streaming_card.update_text(_render_progress() + "\n\n🧠 思考中...")

            response = self._brain.think(messages=messages, tools=self._tools.schemas())
            if response.done or (response.text and not response.tool_calls):
                # Use notify content for card, never raw brain output
                final = notify_content or "分析完成"
                if progress_steps:
                    final = _render_progress() + "\n---\n" + final
                if streaming_card:
                    streaming_card.complete("✅ 分析完成", final, "green")
                return notify_content or response.text or ""

            if response.tool_calls:
                for call in response.tool_calls:
                    # notify: capture content, don't send separate message
                    if call.name == "notify":
                        if notified:
                            messages.append(Message(
                                role="tool_result", content="Already sent.",
                                tool_call_id=call.name,
                            ))
                            continue
                        notified = True
                        notify_content = call.arguments.get("message", "")
                        if streaming_card:
                            streaming_card.update_text(_render_progress() + "\n\n" + notify_content)
                        else:
                            self._tools.execute(call.name, call.arguments)
                        messages.append(Message(role="tool_result", content="OK", tool_call_id=call.name))
                        continue

                    # request_approval: always send as separate card (not in streaming card)
                    if call.name == "request_approval":
                        label = f"📋 提交审批: {call.arguments.get('action', '')}"
                        progress_steps.append(label)
                        if streaming_card:
                            streaming_card.update_text(_render_progress())
                        logger.info(f"Tool call: {call.name}({call.arguments})")
                        result = self._tools.execute(call.name, call.arguments)
                        progress_steps[-1] = f"✅ {label[2:]}"
                        messages.append(Message(role="tool_result", content=str(result), tool_call_id=call.name))
                        continue

                    # Dedup load_skill calls
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

                    # Regular tools: show readable progress
                    label = tool_labels.get(call.name, f"🔧 {call.name}")
                    if call.name == "load_skill":
                        label = f"📚 加载 {call.arguments.get('name', '知识')}"
                    progress_steps.append(f"{label}...")
                    if streaming_card:
                        streaming_card.update_text(_render_progress())

                    logger.info(f"Tool call: {call.name}({call.arguments})")
                    result = self._tools.execute(call.name, call.arguments)
                    messages.append(Message(role="tool_result", content=str(result), tool_call_id=call.name))

                    progress_steps[-1] = f"✅ {label[2:] if label[0] in '📝📊📈📚🔍🌐💾🔧' else label}"
                    if streaming_card:
                        streaming_card.update_text(_render_progress())

                    if call.name == "save_memory":
                        memory_saved = True

            if memory_saved:
                logger.info("Memory saved, stopping agent loop")
                # Build final card: progress steps + analysis result
                parts = []
                if progress_steps:
                    parts.append(_render_progress())
                if notify_content:
                    parts.append("---")
                    parts.append(notify_content)
                final = "\n".join(parts) if parts else "完成"
                if streaming_card:
                    streaming_card.complete("✅ 分析完成", final, "green")
                return response.text or "Task complete."

            if response.text:
                messages.append(Message(role="assistant", content=response.text))

        if streaming_card:
            streaming_card.complete("⚠️ 达到最大迭代", _render_progress(), "yellow")
        return "Max iterations reached"

    def serve(self, schedules: list | None = None) -> None:
        """Start scheduled agent. If schedules not provided, reads from config."""
        feishu = self._channels.get("feishu")

        # Register message handler BEFORE starting WebSocket so it gets registered
        if self._conversation and feishu and hasattr(feishu, 'set_message_handler'):
            def on_message(chat_id: str, text: str):
                self._conversation.add_message("user", text, chat_id)
                ctx = self._conversation.get_context(chat_id)
                context_str = "\n".join(f"[{m['role']}] {m['content']}" for m in ctx[:-1]) if len(ctx) > 1 else ""
                task = f"对话上下文:\n{context_str}\n\n用户消息: {text}" if context_str else text
                result = self.run(task)
                self._conversation.add_message("assistant", result, chat_id)
            feishu.set_message_handler(on_message)
            logger.info("Feishu message handler registered for bidirectional comms")

        # Start WebSocket AFTER handlers are registered
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
