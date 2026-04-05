from __future__ import annotations
from typing import Any, Callable
from x_agent_kit.tools.base import tool


def create_save_memory_tool(memory) -> Callable:
    @tool("Save important information to persistent memory for future sessions.")
    def save_memory(key: str, content: str) -> str:
        memory.save(key, content)
        return f"Memory saved: {key}"
    return save_memory


def create_recall_memories_tool(memory) -> Callable:
    @tool("Recall all saved memories from previous sessions.")
    def recall_memories() -> str:
        return memory.summary()
    return recall_memories

def create_load_skill_tool(loader) -> Callable:
    @tool("Load a skill (domain knowledge) by name. Call this when you need specialized expertise.")
    def load_skill(name: str) -> str:
        """
        Args:
            name: Skill name to load (e.g. 'paid-ads', 'ad-creative')
        """
        return loader.load(name)
    return load_skill

def create_list_skills_tool(loader) -> Callable:
    @tool("List all available skills. Call this to see what domain knowledge is available.")
    def list_skills() -> str:
        names = loader.list()
        return ", ".join(names) if names else "No skills available."
    return list_skills

def create_notify_tool(channels: dict) -> Callable:
    @tool("Send a notification message to the user.")
    def notify(message: str, channel: str = "default") -> bool:
        """
        Args:
            message: Message text to send
            channel: Channel name (default: 'default')
        """
        ch = channels.get(channel, channels.get("default"))
        if ch is None:
            return False
        result = ch.send_text(message)
        return result.get("ok", False)
    return notify

def create_request_approval_tool(channels: dict) -> Callable:
    @tool("Request human approval before executing an action. Blocks until approved or rejected.")
    def request_approval(action: str, details: str, channel: str = "default") -> str:
        """
        Args:
            action: Short description of what needs approval
            details: Full details of the proposed action
            channel: Channel name (default: 'default')
        Returns:
            'APPROVED' or 'REJECTED' or 'TIMEOUT'
        """
        ch = channels.get(channel, channels.get("default"))
        if ch is None:
            return "REJECTED"
        return ch.request_approval(action, details)
    return request_approval
