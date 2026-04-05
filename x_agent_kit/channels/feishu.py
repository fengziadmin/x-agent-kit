from __future__ import annotations
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, PatchMessageRequest, PatchMessageRequestBody
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse
from loguru import logger
from x_agent_kit.channels.base import BaseChannel
from x_agent_kit.channels.feishu_cards import StreamingCard, build_confirmation_card, build_status_card

_APPROVAL_DIR = Path("/tmp/x-agent-approvals")

class FeishuChannel(BaseChannel):
    def __init__(self, app_id: str, app_secret: str, chat_id: str) -> None:
        self._chat_id = chat_id
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).log_level(lark.LogLevel.ERROR).build()
        self._ws_started = False
        self._approval_queue = None
        self._tool_executor = None

    def send_text(self, text: str) -> dict[str, Any]:
        # If text contains markdown, send as card for proper rendering
        if any(mk in text for mk in ("##", "**", "- ", "* ", "```", "1. ")):
            return self._send_markdown_card(text)
        return self._send("text", json.dumps({"text": text}))

    def _send_markdown_card(self, text: str) -> dict[str, Any]:
        """Send long markdown text as a card, split into chunks if needed."""
        # Extract title from first ## heading if present
        title = "Agent Report"
        lines = text.split("\n")
        for line in lines:
            if line.startswith("## "):
                title = line.lstrip("# ").strip()
                break

        # Feishu card markdown has a ~4000 char limit per element, split if needed
        chunks = []
        current = []
        current_len = 0
        for line in lines:
            if current_len + len(line) > 3500 and current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line) + 1
        if current:
            chunks.append("\n".join(current))

        elements = []
        for chunk in chunks:
            elements.append({"tag": "markdown", "content": chunk})
            elements.append({"tag": "hr"})
        if elements and elements[-1]["tag"] == "hr":
            elements.pop()

        card = {
            "schema": "2.0",
            "header": {
                "title": {"content": title, "tag": "plain_text"},
                "template": "blue",
            },
            "body": {"elements": elements},
        }
        return self._send("interactive", json.dumps(card))

    def send_card(self, card: dict[str, Any]) -> dict[str, Any]:
        return self._send("interactive", json.dumps(card))

    def request_approval(self, action: str, details: str, timeout: int = 3600) -> str:
        self._ensure_ws()
        request_id = str(uuid.uuid4())
        card = {
            "schema": "2.0",
            "header": {"title": {"content": f"审批: {action}", "tag": "plain_text"}, "template": "orange"},
            "body": {"elements": [
                {"tag": "markdown", "content": f"**操作**: {action}\n\n{details}"},
                {"tag": "column_set", "columns": [
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "button", "text": {"tag": "plain_text", "content": "Approve"}, "type": "primary", "behaviors": [{"type": "callback", "value": {"request_id": request_id, "decision": "approve"}}]}]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "button", "text": {"tag": "plain_text", "content": "Reject"}, "type": "danger", "behaviors": [{"type": "callback", "value": {"request_id": request_id, "decision": "reject"}}]}]},
                ]},
            ]},
        }
        self.send_card(card)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self._read_approval(request_id)
            if result:
                return result
            time.sleep(2)
        return "TIMEOUT"

    def send_approval_card(self, request_id: str, action: str, details: str) -> dict[str, Any]:
        card = build_confirmation_card(request_id, action, details)
        return self.send_card(card)

    def send_streaming_start(self, title: str = "🤔 分析中...") -> StreamingCard:
        """Create and send a streaming card. Returns StreamingCard for updates."""
        card = StreamingCard(self._client, self._chat_id)
        card.start(title)
        return card

    def set_approval_queue(self, queue) -> None:
        self._approval_queue = queue

    def set_tool_executor(self, executor) -> None:
        """Set a callback to execute tools when approvals are granted."""
        self._tool_executor = executor

    def _send(self, msg_type: str, content: str) -> dict[str, Any]:
        try:
            request = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(CreateMessageRequestBody.builder().receive_id(self._chat_id).msg_type(msg_type).content(content).build()).build()
            response = self._client.im.v1.message.create(request)
            if response.success():
                return {"ok": True, "message_id": response.data.message_id}
            return {"error": response.msg}
        except Exception as exc:
            return {"error": str(exc)}

    def _ensure_ws(self) -> None:
        if self._ws_started:
            return
        handler = lark.EventDispatcherHandler.builder("", "").register_p2_card_action_trigger(self._on_card_action).build()
        ws = lark.ws.Client(app_id=self._app_id, app_secret=self._app_secret, event_handler=handler, log_level=lark.LogLevel.ERROR, auto_reconnect=True)
        threading.Thread(target=ws.start, daemon=True).start()
        self._ws_started = True
        time.sleep(2)

    def _on_card_action(self, trigger: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        resp = P2CardActionTriggerResponse()
        try:
            event = trigger.event
            action = getattr(event, "action", None)
            value = getattr(action, "value", {}) if action else {}
            request_id = value.get("request_id", "")
            decision = value.get("decision", "")
            if request_id and decision:
                status = "APPROVED" if decision == "approve" else "REJECTED"
                _APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
                (_APPROVAL_DIR / f"{request_id}.json").write_text(json.dumps({"status": status}), encoding="utf-8")
                context = getattr(event, "context", None)
                msg_id = getattr(context, "open_message_id", "") if context else ""
                if msg_id:
                    threading.Thread(target=self._patch_card, args=(msg_id, decision, request_id), daemon=True).start()

                if decision == "approve" and self._approval_queue:
                    pending = self._approval_queue.get(request_id)
                    if pending and pending["tool_name"]:
                        self._approval_queue.resolve(request_id, "APPROVED")
                        if self._tool_executor:
                            def execute(p=pending):
                                try:
                                    result = self._tool_executor(p["tool_name"], json.loads(p["tool_args"]))
                                    logger.info(f"Approved action executed: {p['tool_name']} → {str(result)[:100]}")
                                    self.send_text(f"✅ 已执行: {p['action']}\n结果: {str(result)[:500]}")
                                except Exception as exc:
                                    logger.error(f"Failed to execute approved action: {exc}")
                                    self.send_text(f"❌ 执行失败: {p['action']}\n错误: {exc}")
                            threading.Thread(target=execute, daemon=True).start()
                elif decision == "reject" and self._approval_queue:
                    self._approval_queue.resolve(request_id, "REJECTED")
        except Exception as exc:
            logger.error(f"Card callback error: {exc}")
        return resp

    def _patch_card(self, message_id: str, decision: str, request_id: str) -> None:
        time.sleep(1)
        status = "complete" if decision == "approve" else "error"
        title = "✅ 已批准" if decision == "approve" else "❌ 已拒绝"
        action_text = "正在执行..." if decision == "approve" else "操作已取消"
        card = build_status_card(title, status, "green" if decision == "approve" else "red", f"审批请求 `{request_id[:8]}...` {title}，{action_text}")
        try:
            req = PatchMessageRequest.builder().message_id(message_id).request_body(PatchMessageRequestBody.builder().content(json.dumps(card)).build()).build()
            self._client.im.v1.message.patch(req)
        except Exception as exc:
            logger.error(f"Patch card failed: {exc}")

    def _read_approval(self, request_id: str) -> str | None:
        f = _APPROVAL_DIR / f"{request_id}.json"
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("status")
        except Exception:
            return None
