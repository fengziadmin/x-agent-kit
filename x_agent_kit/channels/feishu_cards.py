"""Feishu interactive card system — streaming replies, status updates, confirmation buttons."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import lark_oapi as lark
from lark_oapi.api.cardkit.v1 import (
    CreateCardRequest, CreateCardRequestBody,
    ContentCardElementRequest, ContentCardElementRequestBody,
    SettingsCardRequest, SettingsCardRequestBody,
    UpdateCardRequest, UpdateCardRequestBody,
)
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
from loguru import logger

STREAMING_ELEMENT_ID = "streaming_content"
LOADING_ELEMENT_ID = "loading_icon"


class StreamingCard:
    """Manages a single streaming card lifecycle: thinking → streaming → complete."""

    def __init__(self, client: lark.Client, chat_id: str) -> None:
        self._client = client
        self._chat_id = chat_id
        self._card_id: str | None = None
        self._message_id: str | None = None
        self._sequence = 0
        self._accumulated_text = ""

    def start(self, title: str = "🤔 分析中...") -> bool:
        """Create a streaming card and send it to chat. Returns True on success."""
        card_data = json.dumps({
            "schema": "2.0",
            "config": {"streaming_mode": True},
            "header": {"title": {"content": title, "tag": "plain_text"}, "template": "blue"},
            "body": {"elements": [
                {"tag": "markdown", "content": "正在思考...", "element_id": STREAMING_ELEMENT_ID},
                {"tag": "markdown", "content": "⏳", "element_id": LOADING_ELEMENT_ID},
            ]},
        })

        # Step 1: Create CardKit card entity
        try:
            create_req = CreateCardRequest.builder() \
                .request_body(CreateCardRequestBody.builder()
                    .type("card_json")
                    .data(card_data)
                    .build()
                ).build()
            create_resp = self._client.cardkit.v1.card.create(create_req)
            if not create_resp.success():
                logger.error(f"CardKit create failed: {create_resp.code} {create_resp.msg}")
                return False
            self._card_id = create_resp.data.card_id
            logger.debug(f"CardKit card created: {self._card_id}")
        except Exception as exc:
            logger.error(f"CardKit create error: {exc}")
            return False

        # Step 2: Send card to chat
        try:
            content = json.dumps({"type": "card", "data": {"card_id": self._card_id}})
            send_req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(self._chat_id)
                    .msg_type("interactive")
                    .content(content)
                    .build()
                ).build()
            send_resp = self._client.im.v1.message.create(send_req)
            if send_resp.success():
                self._message_id = send_resp.data.message_id
                logger.debug(f"Streaming card sent: {self._message_id}")
                return True
            else:
                logger.error(f"Send streaming card failed: {send_resp.code} {send_resp.msg}")
                return False
        except Exception as exc:
            logger.error(f"Send streaming card error: {exc}")
            return False

    def update_text(self, text: str) -> None:
        """Update the streaming text content (sends full accumulated text)."""
        if not self._card_id:
            return
        self._accumulated_text = text
        self._sequence += 1
        try:
            req = ContentCardElementRequest.builder() \
                .card_id(self._card_id) \
                .element_id(STREAMING_ELEMENT_ID) \
                .request_body(ContentCardElementRequestBody.builder()
                    .content(text)
                    .sequence(self._sequence)
                    .build()
                ).build()
            resp = self._client.cardkit.v1.card_element.content(req)
            if not resp.success():
                logger.debug(f"CardKit element update failed: {resp.code} {resp.msg}")
        except Exception as exc:
            logger.debug(f"CardKit element update error: {exc}")

    def append_text(self, new_text: str) -> None:
        """Append text to the streaming content."""
        self._accumulated_text += new_text
        self.update_text(self._accumulated_text)

    def complete(self, title: str, content: str, color: str = "green") -> None:
        """Finish streaming and replace with final card."""
        if not self._card_id:
            return

        # Step 1: Update streaming text to final content
        self.update_text(content)

        # Step 2: Clear the loading icon
        self._sequence += 1
        try:
            req = ContentCardElementRequest.builder() \
                .card_id(self._card_id) \
                .element_id(LOADING_ELEMENT_ID) \
                .request_body(ContentCardElementRequestBody.builder()
                    .content("✅")
                    .sequence(self._sequence)
                    .build()
                ).build()
            self._client.cardkit.v1.card_element.content(req)
        except Exception:
            pass

        # Step 3: Close streaming mode
        self._sequence += 1
        try:
            settings_req = SettingsCardRequest.builder() \
                .card_id(self._card_id) \
                .request_body(SettingsCardRequestBody.builder()
                    .settings(json.dumps({"streaming_mode": False}))
                    .sequence(self._sequence)
                    .build()
                ).build()
            self._client.cardkit.v1.card.settings(settings_req)
        except Exception:
            pass

        # Step 4: Update card header via im.message.patch (more reliable than cardkit.update)
        if self._message_id:
            try:
                from lark_oapi.api.im.v1 import PatchMessageRequest, PatchMessageRequestBody
                final_card = json.dumps({
                    "schema": "2.0",
                    "header": {"title": {"content": title, "tag": "plain_text"}, "template": color},
                    "body": {"elements": [
                        {"tag": "markdown", "content": content},
                    ]},
                })
                req = PatchMessageRequest.builder() \
                    .message_id(self._message_id) \
                    .request_body(PatchMessageRequestBody.builder().content(final_card).build()) \
                    .build()
                resp = self._client.im.v1.message.patch(req)
                if resp.success():
                    logger.debug(f"Card patched to complete: {self._message_id}")
                else:
                    logger.debug(f"Card patch failed: {resp.code} {resp.msg}")
            except Exception as exc:
                logger.debug(f"Card patch error: {exc}")


def build_status_card(title: str, status: str, color: str, content: str = "") -> dict:
    """Build a status card (thinking/processing/complete/expired)."""
    status_colors = {"pending": "blue", "processing": "turquoise", "complete": "green", "error": "red", "expired": "grey"}
    template = status_colors.get(status, color)
    tag_text = {"pending": "待处理", "processing": "处理中", "complete": "已完成", "error": "失败", "expired": "已过期"}

    card = {
        "schema": "2.0",
        "header": {
            "title": {"content": title, "tag": "plain_text"},
            "template": template,
            "text_tag_list": [{"tag": "text_tag", "text": {"tag": "plain_text", "content": tag_text.get(status, status)}, "color": template}],
        },
        "body": {"elements": []},
    }
    if content:
        card["body"]["elements"].append({"tag": "markdown", "content": content})
    return card


def build_confirmation_card(request_id: str, action: str, details: str, preview: str = "") -> dict:
    """Build an orange confirmation card with approve/reject buttons."""
    elements = [
        {"tag": "markdown", "content": f"**操作**: {action}\n\n{details}"},
    ]
    if preview:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": f"**预览**:\n{preview}"})

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "column_set",
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 批准"},
                 "type": "primary",
                 "behaviors": [{"type": "callback", "value": {"request_id": request_id, "decision": "approve"}}]},
            ]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                 "type": "danger",
                 "behaviors": [{"type": "callback", "value": {"request_id": request_id, "decision": "reject"}}]},
            ]},
        ],
    })

    return {
        "schema": "2.0",
        "header": {
            "title": {"content": f"⚠️ 审批: {action}", "tag": "plain_text"},
            "template": "orange",
            "text_tag_list": [{"tag": "text_tag", "text": {"tag": "plain_text", "content": "待审批"}, "color": "orange"}],
        },
        "body": {"elements": elements},
    }


# ---------------------------------------------------------------------------
# Plan approval card builders
# ---------------------------------------------------------------------------

_RISK_LABELS = {"high": "🔴 高风险", "medium": "🟡 中风险", "low": "🟢 低风险"}
_PRIORITY_LABELS = {"high": "紧急", "medium": "常规", "low": "低优"}
_TYPE_LABELS = {"daily": "日常计划", "weekly": "周度策略", "monthly": "月度复盘"}


_STEP_STATUS_LABELS = {
    "approved": "✅ 已批准",
    "rejected": "❌ 已拒绝",
    "executed": "✅ 已执行",
    "failed": "❌ 执行失败",
    "negotiating": "💬 协商中",
}


def build_plan_approval_card(plan) -> dict:
    """Build an orange plan approval card with per-step approve/reject buttons.

    Steps that have already been approved/rejected show a status label instead of buttons.
    This allows the card to be patched in-place after each decision without losing other steps.
    """
    from x_agent_kit.plan import Plan  # noqa: F811 — deferred to avoid circular imports

    type_label = _TYPE_LABELS.get(plan.plan_type, plan.plan_type)
    step_count = len(plan.steps)

    # Count decided steps
    decided = sum(1 for s in plan.steps if s.status not in ("pending",))
    pending = step_count - decided

    elements: list[dict] = [
        {"tag": "markdown", "content": f"**摘要**: {plan.summary}"},
        {"tag": "hr"},
    ]

    for step in plan.steps:
        risk_label = _RISK_LABELS.get(step.risk_level, step.risk_level)
        priority_label = _PRIORITY_LABELS.get(step.priority, step.priority)

        if step.status in _STEP_STATUS_LABELS:
            # Already decided — show status text instead of buttons
            status_text = _STEP_STATUS_LABELS[step.status]
            elements.append(
                {"tag": "markdown", "content": f"{risk_label}  |  **{priority_label}**\n{step.action}\n\n**{status_text}**"}
            )
        else:
            # Pending — show approve/reject buttons
            elements.append(
                {"tag": "markdown", "content": f"{risk_label}  |  **{priority_label}**\n{step.action}"}
            )
            elements.append({
                "tag": "column_set",
                "columns": [
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 批准"},
                         "type": "primary",
                         "behaviors": [{"type": "callback", "value": {
                             "plan_id": plan.plan_id, "step_id": step.step_id, "decision": "approve"}}]},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                         "type": "danger",
                         "behaviors": [{"type": "callback", "value": {
                             "plan_id": plan.plan_id, "step_id": step.step_id, "decision": "reject"}}]},
                    ]},
                ],
            })
        elements.append({"tag": "hr"})

    # Header color: orange if pending, green if all approved/executed, red if any rejected
    if pending == 0 and all(s.status in ("approved", "executed") for s in plan.steps):
        header_color = "green"
        header_title = f"✅ {plan.title}"
    elif pending == 0:
        header_color = "blue"
        header_title = f"📋 {plan.title} (已处理)"
    else:
        header_color = "orange"
        header_title = f"📋 {plan.title}"

    return {
        "schema": "2.0",
        "header": {
            "title": {"content": header_title, "tag": "plain_text"},
            "template": header_color,
            "text_tag_list": [
                {"tag": "text_tag", "text": {"tag": "plain_text", "content": type_label}, "color": "orange"},
                {"tag": "text_tag", "text": {"tag": "plain_text", "content": f"全部通过 ✅" if pending == 0 and all(s.status in ("approved", "executed") for s in plan.steps) else f"{pending} 项待审批 / 共 {step_count} 项"}, "color": "green" if pending == 0 else "turquoise"},
            ],
        },
        "body": {"elements": elements},
    }


def build_step_result_card(step, result: str) -> dict:
    """Build a result card after step execution — green for success, red for failure."""
    is_failed = step.status == "failed"
    template = "red" if is_failed else "green"
    icon = "❌" if is_failed else "✅"
    status_text = "执行失败" if is_failed else "执行成功"

    return {
        "schema": "2.0",
        "header": {
            "title": {"content": f"{icon} {status_text}: {step.action}", "tag": "plain_text"},
            "template": template,
        },
        "body": {"elements": [
            {"tag": "markdown", "content": f"**操作**: {step.action}"},
            {"tag": "hr"},
            {"tag": "markdown", "content": f"**结果**: {result}"},
        ]},
    }


def build_negotiation_card(step, new_proposal: str) -> dict:
    """Build a blue negotiation card for re-proposing a rejected step."""
    elements: list[dict] = []

    if step.rejection_note:
        elements.append({"tag": "markdown", "content": f"**拒绝原因**: {step.rejection_note}"})
        elements.append({"tag": "hr"})

    elements.append({"tag": "markdown", "content": f"**新方案**: {new_proposal}"})
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "column_set",
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 批准"},
                 "type": "primary",
                 "behaviors": [{"type": "callback", "value": {
                     "step_id": step.step_id, "decision": "approve"}}]},
            ]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "💬 继续讨论"},
                 "type": "default",
                 "behaviors": [{"type": "callback", "value": {
                     "step_id": step.step_id, "decision": "discuss"}}]},
            ]},
        ],
    })

    return {
        "schema": "2.0",
        "header": {
            "title": {"content": f"🔄 协商: {step.action}", "tag": "plain_text"},
            "template": "blue",
        },
        "body": {"elements": elements},
    }
