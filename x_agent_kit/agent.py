from __future__ import annotations
from pathlib import Path
from typing import Any
from loguru import logger
from x_agent_kit.config import Config, load_config
from x_agent_kit.models import BrainResponse, Message
from x_agent_kit.skills.loader import SkillLoader
from x_agent_kit.tools.builtin import create_list_skills_tool, create_load_skill_tool, create_notify_tool, create_request_approval_tool, create_save_memory_tool, create_recall_memories_tool, create_search_memory_tool
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

            # Wire up feishu channel for async execution
            feishu = self._channels.get("feishu")
            if feishu and hasattr(feishu, 'set_approval_queue'):
                feishu.set_approval_queue(self._approval_queue)
                feishu.set_tool_executor(lambda name, args: self._tools.execute(name, args))
                feishu._ensure_ws()  # Start WebSocket listener

        self._tools.register(create_request_approval_tool(self._channels, self._approval_queue))

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

        for i in range(max_iter):
            logger.info(f"Agent iteration {i+1}/{max_iter}")
            response = self._brain.think(messages=messages, tools=self._tools.schemas())
            if response.done or (response.text and not response.tool_calls):
                return response.text or ""
            if response.tool_calls:
                for call in response.tool_calls:
                    # Prevent duplicate notify calls
                    if call.name == "notify":
                        if notified:
                            logger.info("Skipping duplicate notify call")
                            messages.append(Message(
                                role="tool_result", content="Already sent. Do not notify again.",
                                tool_call_id=call.name,
                            ))
                            continue
                        notified = True

                    logger.info(f"Tool call: {call.name}({call.arguments})")
                    result = self._tools.execute(call.name, call.arguments)
                    messages.append(Message(role="tool_result", content=str(result), tool_call_id=call.name))

                    # Auto-stop after save_memory (it's the last step)
                    if call.name == "save_memory":
                        memory_saved = True

            if memory_saved:
                logger.info("Memory saved, stopping agent loop")
                return response.text or "Task complete."

            if response.text:
                messages.append(Message(role="assistant", content=response.text))
        return "Max iterations reached"

    def serve(self, schedules: list | None = None) -> None:
        """Start scheduled agent. If schedules not provided, reads from config."""
        from x_agent_kit.scheduler import Scheduler
        sched = Scheduler()
        items = schedules or self._config.schedules
        for s in items:
            cron_expr = s.cron if hasattr(s, 'cron') else s['cron']
            task_str = s.task if hasattr(s, 'task') else s['task']
            logger.info(f"Schedule: {cron_expr} -> {task_str[:50]}...")
            sched.add(cron_expr, lambda t=task_str: self.run(t))
        sched.start()
