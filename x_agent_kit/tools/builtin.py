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


# ---------------------------------------------------------------------------
# Plan tools
# ---------------------------------------------------------------------------

def create_plan_tool(plan_manager) -> Callable:
    @tool("Create a structured execution plan from a list of steps. Returns the plan ID.")
    def create_plan(title: str, summary: str, plan_type: str, steps: str) -> str:
        """
        Args:
            title: Plan title
            summary: Brief description of the plan
            plan_type: One of 'daily', 'weekly', 'monthly'
            steps: JSON array of step objects, each with keys: action, tool_name, tool_args, priority, risk_level
        """
        parsed_steps = json.loads(steps)
        plan = plan_manager.create(title, summary, plan_type, parsed_steps)
        return json.dumps({"plan_id": plan.plan_id, "steps_count": len(plan.steps)})
    return create_plan


def create_submit_plan_tool(plan_manager, channels: dict) -> Callable:
    @tool("Submit a plan for human approval via Feishu. Sends an interactive approval card.")
    def submit_plan(plan_id: str) -> str:
        """
        Args:
            plan_id: The plan ID to submit for approval
        """
        from x_agent_kit.channels.feishu_cards import build_plan_approval_card

        plan = plan_manager.get(plan_id)
        if plan is None:
            return json.dumps({"error": f"Plan {plan_id} not found"})

        card = build_plan_approval_card(plan)
        ch = channels.get("default")
        if ch is None:
            return json.dumps({"error": "No default channel configured"})

        ch.send_card(card)
        plan_manager._conn.execute(
            "UPDATE plans SET status = 'pending_approval' WHERE plan_id = ?", (plan_id,)
        )
        plan_manager._conn.commit()
        return json.dumps({"status": "submitted", "plan_id": plan_id})
    return submit_plan


def create_get_plan_tool(plan_manager) -> Callable:
    @tool("Get the current status of a plan and all its steps as JSON.")
    def get_plan(plan_id: str) -> str:
        """
        Args:
            plan_id: The plan ID to retrieve
        """
        plan = plan_manager.get(plan_id)
        if plan is None:
            return json.dumps({"error": f"Plan {plan_id} not found"})
        return json.dumps({
            "plan_id": plan.plan_id,
            "title": plan.title,
            "summary": plan.summary,
            "plan_type": plan.plan_type,
            "status": plan.status,
            "created_at": plan.created_at,
            "resolved_at": plan.resolved_at,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args,
                    "priority": s.priority,
                    "risk_level": s.risk_level,
                    "status": s.status,
                    "rejection_note": s.rejection_note,
                    "execution_result": s.execution_result,
                }
                for s in plan.steps
            ],
        }, ensure_ascii=False)
    return get_plan


def create_execute_approved_steps_tool(plan_manager, tool_executor, channels: dict) -> Callable:
    @tool("Execute all approved steps in a plan. Skips non-approved steps. Reports results via Feishu card.")
    def execute_approved_steps(plan_id: str) -> str:
        """
        Args:
            plan_id: The plan ID whose approved steps should be executed
        """
        from x_agent_kit.channels.feishu_cards import build_step_result_card

        plan = plan_manager.get(plan_id)
        if plan is None:
            return json.dumps({"error": f"Plan {plan_id} not found"})

        executed = 0
        failed = 0
        for step in plan.steps:
            if step.status != "approved":
                continue
            result_text = ""
            try:
                result = tool_executor(step.tool_name, step.tool_args)
                result_text = str(result)
                plan_manager.set_step_result(plan_id, step.step_id, result_text)
                executed += 1
            except Exception as exc:
                result_text = str(exc)
                plan_manager.update_step_status(plan_id, step.step_id, "failed", note=result_text)
                failed += 1

            # Send result card
            ch = channels.get("default")
            if ch is not None:
                updated_plan = plan_manager.get(plan_id)
                updated_step = next((s for s in updated_plan.steps if s.step_id == step.step_id), None)
                if updated_step:
                    card = build_step_result_card(updated_step, result_text)
                    ch.send_card(card)

        plan_manager.refresh_plan_status(plan_id)
        return json.dumps({"executed": executed, "failed": failed, "plan_id": plan_id})
    return execute_approved_steps


def create_update_step_tool(plan_manager) -> Callable:
    @tool("Update a plan step's action, tool, or arguments after negotiation.")
    def update_step(plan_id: str, step_id: str, new_action: str, new_tool_name: str, new_tool_args: str = "{}") -> str:
        """
        Args:
            plan_id: The plan ID containing the step
            step_id: The step ID to update
            new_action: Updated action description
            new_tool_name: Updated tool name
            new_tool_args: Updated tool arguments as JSON string
        """
        args_dict = json.loads(new_tool_args)
        plan_manager.update_step_action(plan_id, step_id, new_action, new_tool_name, args_dict)
        return json.dumps({"status": "updated", "step_id": step_id})
    return update_step


def create_resubmit_step_tool(plan_manager, channels: dict) -> Callable:
    @tool("Resubmit a rejected step for re-approval after modification. Sends a negotiation card.")
    def resubmit_step(plan_id: str, step_id: str) -> str:
        """
        Args:
            plan_id: The plan ID containing the step
            step_id: The step ID to resubmit
        """
        from x_agent_kit.channels.feishu_cards import build_negotiation_card

        plan = plan_manager.get(plan_id)
        if plan is None:
            return json.dumps({"error": f"Plan {plan_id} not found"})

        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if step is None:
            return json.dumps({"error": f"Step {step_id} not found"})

        # Reset status to pending
        plan_manager.update_step_status(plan_id, step_id, "pending")

        # Send negotiation card
        ch = channels.get("default")
        if ch is not None:
            card = build_negotiation_card(step, step.action)
            ch.send_card(card)

        return json.dumps({"status": "resubmitted", "step_id": step_id})
    return resubmit_step
