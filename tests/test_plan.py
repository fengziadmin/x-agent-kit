from __future__ import annotations
import pytest
from x_agent_kit.plan import Plan, PlanStep, PlanManager


def _make_manager() -> PlanManager:
    return PlanManager(db_path=":memory:")


def _sample_steps() -> list[dict]:
    return [
        {
            "action": "Campaign A budget 100→150",
            "tool_name": "update_budget",
            "tool_args": {"campaign_resource": "customers/123/campaigns/456", "budget_dollars": 150},
            "priority": "high",
            "risk_level": "medium",
        },
        {
            "action": "Pause keyword 'free trial'",
            "tool_name": "pause_keyword",
            "tool_args": {"criterion_resource": "customers/123/adGroupCriteria/789~111"},
            "priority": "medium",
            "risk_level": "low",
        },
    ]


class TestPlanManager:
    def test_create_plan(self):
        mgr = _make_manager()
        plan = mgr.create("Daily Plan 4/5", "ROAS is strong, increase budget", "daily", _sample_steps())
        assert plan.plan_id
        assert plan.title == "Daily Plan 4/5"
        assert plan.summary == "ROAS is strong, increase budget"
        assert plan.plan_type == "daily"
        assert plan.status == "draft"
        assert len(plan.steps) == 2
        assert plan.steps[0].action == "Campaign A budget 100→150"
        assert plan.steps[0].status == "pending"
        assert plan.steps[0].tool_name == "update_budget"
        assert plan.steps[1].priority == "medium"

    def test_get_plan(self):
        mgr = _make_manager()
        created = mgr.create("Test", "summary", "daily", _sample_steps())
        fetched = mgr.get(created.plan_id)
        assert fetched is not None
        assert fetched.plan_id == created.plan_id
        assert len(fetched.steps) == 2

    def test_get_nonexistent(self):
        mgr = _make_manager()
        assert mgr.get("nonexistent-id") is None

    def test_list_plans(self):
        mgr = _make_manager()
        mgr.create("Daily 1", "s", "daily", _sample_steps())
        mgr.create("Weekly 1", "s", "weekly", _sample_steps())
        mgr.create("Daily 2", "s", "daily", _sample_steps())
        assert len(mgr.list_plans()) == 3
        assert len(mgr.list_plans(plan_type="daily")) == 2
        assert len(mgr.list_plans(plan_type="weekly")) == 1

    def test_list_plans_by_status(self):
        mgr = _make_manager()
        p1 = mgr.create("P1", "s", "daily", _sample_steps())
        mgr.create("P2", "s", "daily", _sample_steps())
        mgr._conn.execute("UPDATE plans SET status = 'completed' WHERE plan_id = ?", (p1.plan_id,))
        mgr._conn.commit()
        assert len(mgr.list_plans(status="draft")) == 1
        assert len(mgr.list_plans(status="completed")) == 1

    def test_update_step_status_approve(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        step_id = plan.steps[0].step_id
        mgr.update_step_status(plan.plan_id, step_id, "approved")
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].status == "approved"

    def test_update_step_status_reject_with_note(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        step_id = plan.steps[1].step_id
        mgr.update_step_status(plan.plan_id, step_id, "rejected", note="Budget too high")
        updated = mgr.get(plan.plan_id)
        assert updated.steps[1].status == "rejected"
        assert updated.steps[1].rejection_note == "Budget too high"

    def test_update_step_action(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        step_id = plan.steps[0].step_id
        mgr.update_step_action(plan.plan_id, step_id, "Budget 100→120", "update_budget", {"budget_dollars": 120})
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].action == "Budget 100→120"
        assert updated.steps[0].tool_args == {"budget_dollars": 120}

    def test_set_step_result(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        step_id = plan.steps[0].step_id
        mgr.update_step_status(plan.plan_id, step_id, "approved")
        mgr.set_step_result(plan.plan_id, step_id, "Budget updated successfully")
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].execution_result == "Budget updated successfully"
        assert updated.steps[0].status == "executed"

    def test_refresh_plan_status_all_executed(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        for step in plan.steps:
            mgr.update_step_status(plan.plan_id, step.step_id, "approved")
            mgr.set_step_result(plan.plan_id, step.step_id, "done")
        mgr.refresh_plan_status(plan.plan_id)
        updated = mgr.get(plan.plan_id)
        assert updated.status == "completed"

    def test_refresh_plan_status_partial(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        mgr.update_step_status(plan.plan_id, plan.steps[0].step_id, "approved")
        mgr.update_step_status(plan.plan_id, plan.steps[1].step_id, "rejected")
        mgr.refresh_plan_status(plan.plan_id)
        updated = mgr.get(plan.plan_id)
        assert updated.status == "partial_approved"

    def test_refresh_plan_status_pending_approval(self):
        mgr = _make_manager()
        plan = mgr.create("Test", "s", "daily", _sample_steps())
        mgr._conn.execute("UPDATE plans SET status = 'pending_approval' WHERE plan_id = ?", (plan.plan_id,))
        mgr._conn.commit()
        mgr.refresh_plan_status(plan.plan_id)
        updated = mgr.get(plan.plan_id)
        assert updated.status == "pending_approval"
