from __future__ import annotations
import json
from unittest.mock import MagicMock
from x_agent_kit.plan import PlanManager
from x_agent_kit.tools.builtin import (
    create_plan_tool, create_submit_plan_tool, create_get_plan_tool,
    create_execute_approved_steps_tool, create_update_step_tool, create_resubmit_step_tool,
)

def _make_plan_manager() -> PlanManager:
    return PlanManager(db_path=":memory:")

def _sample_steps_json() -> str:
    return json.dumps([
        {"action": "Budget 100→150", "tool_name": "update_budget",
         "tool_args": {"budget_dollars": 150}, "priority": "high", "risk_level": "medium"},
    ])

class TestCreatePlanTool:
    def test_creates_plan(self):
        mgr = _make_plan_manager()
        tool_fn = create_plan_tool(mgr)
        result = tool_fn(title="Test Plan", summary="Test", plan_type="daily", steps=_sample_steps_json())
        assert "plan_id" in result

    def test_returns_plan_id(self):
        mgr = _make_plan_manager()
        tool_fn = create_plan_tool(mgr)
        result = tool_fn(title="Test", summary="s", plan_type="daily", steps=_sample_steps_json())
        parsed = json.loads(result)
        assert "plan_id" in parsed

class TestSubmitPlanTool:
    def test_submit_sends_card(self):
        mgr = _make_plan_manager()
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        channel = MagicMock()
        channel.send_card.return_value = {"ok": True}
        channels = {"default": channel}
        tool_fn = create_submit_plan_tool(mgr, channels)
        result = tool_fn(plan_id=plan.plan_id)
        channel.send_card.assert_called_once()
        assert "submitted" in result.lower() or "提交" in result

class TestGetPlanTool:
    def test_returns_plan_json(self):
        mgr = _make_plan_manager()
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        tool_fn = create_get_plan_tool(mgr)
        result = tool_fn(plan_id=plan.plan_id)
        parsed = json.loads(result)
        assert parsed["title"] == "Test"
        assert len(parsed["steps"]) == 1

class TestExecuteApprovedStepsTool:
    def test_executes_approved_steps(self):
        mgr = _make_plan_manager()
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "mock_tool", "tool_args": {"x": 1}, "priority": "high", "risk_level": "low"},
        ])
        mgr.update_step_status(plan.plan_id, plan.steps[0].step_id, "approved")
        executor = MagicMock(return_value="done")
        channels = {"default": MagicMock()}
        channels["default"].send_card.return_value = {"ok": True}
        tool_fn = create_execute_approved_steps_tool(mgr, executor, channels)
        result = tool_fn(plan_id=plan.plan_id)
        executor.assert_called_once_with("mock_tool", {"x": 1})
        assert "1" in result

class TestUpdateStepTool:
    def test_updates_step(self):
        mgr = _make_plan_manager()
        plan = mgr.create("Test", "s", "daily", [
            {"action": "old", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        tool_fn = create_update_step_tool(mgr)
        tool_fn(plan_id=plan.plan_id, step_id=plan.steps[0].step_id, new_action="new", new_tool_name="t2", new_tool_args='{"y": 2}')
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].action == "new"
        assert updated.steps[0].tool_name == "t2"

class TestResubmitStepTool:
    def test_resubmits_step(self):
        mgr = _make_plan_manager()
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        mgr.update_step_status(plan.plan_id, plan.steps[0].step_id, "rejected", note="no")
        channel = MagicMock()
        channel.send_card.return_value = {"ok": True}
        channels = {"default": channel}
        tool_fn = create_resubmit_step_tool(mgr, channels)
        result = tool_fn(plan_id=plan.plan_id, step_id=plan.steps[0].step_id)
        channel.send_card.assert_called_once()
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].status == "pending"
