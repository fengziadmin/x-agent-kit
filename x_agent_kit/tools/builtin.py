from __future__ import annotations
import json
from typing import Any, Callable
from x_agent_kit.tools.base import tool


def create_save_memory_tool(memory) -> Callable:
    @tool("Save important information to persistent memory for future sessions.")
    def save_memory(key: str, content: str) -> str:
        memory.save(key, content)
        return f"Memory saved: {key}"
    return save_memory


def create_recall_memories_tool(memory) -> Callable:
    @tool("Recall recent memories from previous sessions. Use search_memory for specific topics.")
    def recall_memories() -> str:
        return memory.summary()
    return recall_memories


def create_search_memory_tool(memory) -> Callable:
    @tool("Search past memories by keyword. Use this to find specific information from previous sessions.")
    def search_memory(query: str, limit: int = 5) -> str:
        """
        Args:
            query: Keywords to search for in memories
            limit: Max number of results (default 5)
        """
        results = memory.search(query, limit)
        if not results:
            return f"No memories found matching '{query}'."
        parts = []
        for r in results:
            parts.append(f"**[{r['timestamp'][:16]}] {r['key']}**\n{r['content'][:500]}")
        return "\n\n".join(parts)
    return search_memory


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

def create_request_approval_tool(channels: dict, approval_queue=None) -> Callable:
    @tool("Submit an action for human approval. Does NOT block — the action will be executed when approved.")
    def request_approval(action: str, details: str, tool_name: str = "", tool_args: str = "") -> str:
        """
        Args:
            action: Short description of what needs approval
            details: Full details of the proposed action
            tool_name: Name of the tool to execute when approved (e.g. 'pause_campaign')
            tool_args: JSON string of arguments to pass to the tool (e.g. '{"campaign_resource": "xxx"}')
        Returns:
            Confirmation that approval request was sent
        """
        import uuid
        request_id = str(uuid.uuid4())

        # Save to queue if available
        if approval_queue is not None and tool_name:
            try:
                args_dict = json.loads(tool_args) if isinstance(tool_args, str) and tool_args else {}
            except json.JSONDecodeError:
                args_dict = {}
            approval_queue.add(request_id, action, details, tool_name, args_dict)

        ch = channels.get("default")
        if ch is None:
            return f"Approval queued: {request_id} (no channel)"

        # Send approval card
        ch.send_approval_card(request_id, action, details)
        return f"Approval request sent: {request_id}. Action '{tool_name}' will execute when approved."
    return request_approval
