from __future__ import annotations
import json
from x_agent_kit.i18n import set_locale
set_locale("zh_CN")
from x_agent_kit.plan import Plan, PlanStep
from x_agent_kit.channels.feishu_cards import (
    build_plan_approval_card,
    build_step_result_card,
    build_negotiation_card,
)

def _sample_plan() -> Plan:
    return Plan(
        plan_id="plan-001",
        title="4月5日优化计划",
        summary="Campaign A ROAS=3.2，表现优异。建议追加预算并暂停低效关键词。",
        plan_type="daily",
        steps=[
            PlanStep(step_id="step-001", action="Campaign A 日预算 100→150",
                tool_name="update_budget",
                tool_args={"campaign_resource": "customers/123/campaigns/456", "budget_dollars": 150},
                priority="high", risk_level="medium"),
            PlanStep(step_id="step-002", action="暂停关键词 'free trial'",
                tool_name="pause_keyword",
                tool_args={"criterion_resource": "customers/123/adGroupCriteria/789~111"},
                priority="medium", risk_level="low"),
        ],
        created_at="2026-04-05T09:00:00",
    )

class TestBuildPlanApprovalCard:
    def test_card_has_header_with_title(self):
        card = build_plan_approval_card(_sample_plan())
        assert card["header"]["title"]["content"] == "📋 4月5日优化计划"

    def test_card_has_summary_section(self):
        card = build_plan_approval_card(_sample_plan())
        elements = card["body"]["elements"]
        assert elements[0]["tag"] == "markdown"
        assert "ROAS=3.2" in elements[0]["content"]

    def test_card_has_buttons_per_step(self):
        card = build_plan_approval_card(_sample_plan())
        card_json = json.dumps(card)
        assert "step-001" in card_json
        assert "step-002" in card_json
        assert "approve" in card_json
        assert "reject" in card_json

    def test_card_contains_plan_id(self):
        card_json = json.dumps(build_plan_approval_card(_sample_plan()))
        assert "plan-001" in card_json

    def test_card_has_risk_level_tags(self):
        card_json = json.dumps(build_plan_approval_card(_sample_plan()), ensure_ascii=False)
        assert "中风险" in card_json or "medium" in card_json.lower()

    def test_card_has_plan_type_tag(self):
        card = build_plan_approval_card(_sample_plan())
        tags = card["header"].get("text_tag_list", [])
        assert any("日常" in str(t) or "daily" in str(t).lower() for t in tags)

class TestBuildStepResultCard:
    def test_success_card(self):
        step = _sample_plan().steps[0]
        card = build_step_result_card(step, "Budget updated to $150")
        assert card["header"]["template"] == "green"
        assert "Budget updated" in json.dumps(card)

    def test_failure_card(self):
        step = _sample_plan().steps[0]
        step.status = "failed"
        card = build_step_result_card(step, "API error: quota exceeded")
        assert card["header"]["template"] == "red"
        assert "API error" in json.dumps(card)

class TestBuildNegotiationCard:
    def test_negotiation_card_has_new_proposal(self):
        step = _sample_plan().steps[0]
        step.status = "rejected"
        step.rejection_note = "Too aggressive"
        card = build_negotiation_card(step, "Campaign A 日预算 100→120 (调整后)")
        card_json = json.dumps(card, ensure_ascii=False)
        assert "100→120" in card_json
        assert "approve" in card_json
