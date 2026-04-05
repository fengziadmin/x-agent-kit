from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
from x_agent_kit.plan import PlanManager

class TestFeishuPlanHandler:
    def _make_feishu_channel(self):
        with patch("x_agent_kit.channels.feishu.lark") as mock_lark:
            mock_client = MagicMock()
            mock_lark.Client.builder.return_value.app_id.return_value.app_secret.return_value.log_level.return_value.build.return_value = mock_client
            from x_agent_kit.channels.feishu import FeishuChannel
            ch = FeishuChannel("app_id", "secret", "chat_id")
            ch._client = mock_client
            return ch

    def test_approve_plan_step(self):
        ch = self._make_feishu_channel()
        mgr = PlanManager(db_path=":memory:")
        ch.set_plan_manager(mgr)
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        trigger = MagicMock()
        trigger.event.action.value = {
            "plan_id": plan.plan_id, "step_id": plan.steps[0].step_id, "decision": "approve",
        }
        trigger.event.context.open_message_id = "msg-123"
        ch._on_card_action(trigger)
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].status == "approved"

    def test_reject_plan_step(self):
        ch = self._make_feishu_channel()
        mgr = PlanManager(db_path=":memory:")
        ch.set_plan_manager(mgr)
        plan = mgr.create("Test", "s", "daily", [
            {"action": "a", "tool_name": "t", "tool_args": {}, "priority": "high", "risk_level": "low"},
        ])
        trigger = MagicMock()
        trigger.event.action.value = {
            "plan_id": plan.plan_id, "step_id": plan.steps[0].step_id, "decision": "reject",
        }
        trigger.event.context.open_message_id = "msg-123"
        ch._on_card_action(trigger)
        updated = mgr.get(plan.plan_id)
        assert updated.steps[0].status == "rejected"

    def test_legacy_approval_still_works(self):
        ch = self._make_feishu_channel()
        trigger = MagicMock()
        trigger.event.action.value = {"request_id": "req-123", "decision": "approve"}
        trigger.event.context.open_message_id = "msg-456"
        # Should not error even without plan_manager
        ch._on_card_action(trigger)
