from __future__ import annotations
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, PatchMessageRequest, PatchMessageRequestBody, ReplyMessageRequest, ReplyMessageRequestBody, CreateMessageReactionRequest, CreateMessageReactionRequestBody, DeleteMessageReactionRequest
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
        self._plan_manager = None
        self._message_handler = None
        self._handled_messages: set[str] = set()

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

    def set_plan_manager(self, plan_manager) -> None:
        self._plan_manager = plan_manager

    def set_message_handler(self, handler) -> None:
        self._message_handler = handler

    def _get_bot_open_id(self) -> str:
        """Get and cache the bot's open_id via Feishu API."""
        if not hasattr(self, "_bot_open_id_cache"):
            self._bot_open_id_cache = ""
            try:
                from lark_oapi.api.bot.v3 import BotInfoRequest
                req = BotInfoRequest.builder().build()
                resp = self._client.bot.v3.bot_info.get(req)
                if resp.success() and resp.data and resp.data.bot:
                    self._bot_open_id_cache = resp.data.bot.open_id or ""
                    logger.debug(f"Bot open_id: {self._bot_open_id_cache}")
            except Exception as exc:
                logger.debug(f"Failed to get bot open_id: {exc}")
        return self._bot_open_id_cache

    def add_reaction(self, message_id: str, emoji: str = "OnIt") -> str | None:
        """Add an emoji reaction to a message. Returns reaction_id or None."""
        try:
            req = CreateMessageReactionRequest.builder().message_id(message_id).request_body(
                CreateMessageReactionRequestBody.builder().reaction_type({"emoji_type": emoji}).build()
            ).build()
            resp = self._client.im.v1.message_reaction.create(req)
            if resp.success() and resp.data:
                return resp.data.reaction_id
        except Exception as exc:
            logger.debug(f"Add reaction failed: {exc}")
        return None

    def remove_reaction(self, message_id: str, reaction_id: str) -> None:
        """Remove a reaction from a message."""
        try:
            req = DeleteMessageReactionRequest.builder().message_id(message_id).reaction_id(reaction_id).build()
            self._client.im.v1.message_reaction.delete(req)
        except Exception as exc:
            logger.debug(f"Remove reaction failed: {exc}")

    def reply_text(self, message_id: str, text: str) -> dict[str, Any]:
        """Reply to a specific message (thread reply). Uses card for markdown rendering."""
        try:
            card = {
                "schema": "2.0",
                "body": {"elements": [{"tag": "markdown", "content": text}]},
            }
            content = json.dumps(card)
            req = ReplyMessageRequest.builder().message_id(message_id).request_body(
                ReplyMessageRequestBody.builder().msg_type("interactive").content(content).build()
            ).build()
            response = self._client.im.v1.message.reply(req)
            if response.success():
                return {"ok": True, "message_id": response.data.message_id}
            return {"error": response.msg}
        except Exception as exc:
            return {"error": str(exc)}

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
        self._ws_start_time = int(time.time() * 1000)  # ms timestamp, ignore messages before this
        builder = lark.EventDispatcherHandler.builder("", "")
        builder = builder.register_p2_card_action_trigger(self._on_card_action)
        if self._message_handler:
            builder = builder.register_p2_im_message_receive_v1(self._on_message_receive)
        handler = builder.build()
        ws = lark.ws.Client(app_id=self._app_id, app_secret=self._app_secret, event_handler=handler, log_level=lark.LogLevel.ERROR, auto_reconnect=True)
        threading.Thread(target=ws.start, daemon=True).start()
        self._ws_started = True
        time.sleep(2)

    def _on_message_receive(self, event) -> None:
        """Handle incoming Feishu messages."""
        try:
            msg = event.event.message
            sender = event.event.sender
            sender_type = getattr(sender, "sender_type", "")
            if sender_type == "app":
                return
            msg_type = getattr(msg, "message_type", "")
            if msg_type != "text":
                return
            # Ignore messages sent before WebSocket started (history replay)
            create_time = getattr(msg, "create_time", "0")
            try:
                msg_ts = int(create_time)
            except (ValueError, TypeError):
                msg_ts = 0
            if msg_ts and hasattr(self, "_ws_start_time") and msg_ts < self._ws_start_time:
                return
            message_id = getattr(msg, "message_id", "")
            # Deduplicate — Feishu WebSocket may redeliver the same message
            if message_id in self._handled_messages:
                return
            self._handled_messages.add(message_id)
            # Keep set bounded
            if len(self._handled_messages) > 500:
                self._handled_messages = set(list(self._handled_messages)[-200:])
            chat_id = getattr(msg, "chat_id", "")
            chat_type = getattr(msg, "chat_type", "")
            # In group chats, only respond when @bot is mentioned
            if chat_type == "group":
                mentions = getattr(msg, "mentions", None) or []
                bot_open_id = self._get_bot_open_id()
                bot_mentioned = False
                for m in mentions:
                    m_id = getattr(m, "id", None)
                    if m_id:
                        open_id = getattr(m_id, "open_id", "") if hasattr(m_id, "open_id") else m_id.get("open_id", "") if isinstance(m_id, dict) else ""
                        if open_id and bot_open_id and open_id == bot_open_id:
                            bot_mentioned = True
                            break
                if not bot_mentioned:
                    return
            content_str = getattr(msg, "content", "{}")
            try:
                content = json.loads(content_str)
                text = content.get("text", "")
            except (json.JSONDecodeError, AttributeError):
                text = str(content_str)
            if not text.strip():
                return
            # Remove @mention tags from text
            import re
            text = re.sub(r"@_user_\d+\s*", "", text).strip()
            if not text:
                return
            if self._message_handler:
                self._message_handler(chat_id, text, message_id)
        except Exception as exc:
            logger.error(f"Message receive error: {exc}")

    def _on_card_action(self, trigger: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        resp = P2CardActionTriggerResponse()
        try:
            event = trigger.event
            action = getattr(event, "action", None)
            value = getattr(action, "value", {}) if action else {}
            decision = value.get("decision", "")
            plan_id = value.get("plan_id", "")
            step_id = value.get("step_id", "")
            context = getattr(event, "context", None)
            msg_id = getattr(context, "open_message_id", "") if context else ""

            # --- Plan step approval path ---
            if plan_id and step_id and self._plan_manager:
                new_status = "approved" if decision == "approve" else "rejected"
                self._plan_manager.update_step_status(plan_id, step_id, new_status)
                self._plan_manager.refresh_plan_status(plan_id)
                if msg_id:
                    threading.Thread(
                        target=self._patch_plan_step_card, args=(msg_id, decision, plan_id, step_id), daemon=True
                    ).start()
                # Auto-execute approved step immediately
                if decision == "approve" and self._tool_executor:
                    plan = self._plan_manager.get(plan_id)
                    step = next((s for s in plan.steps if s.step_id == step_id), None) if plan else None
                    if step and step.tool_name:
                        def execute_step(p_id=plan_id, s_id=step_id, s=step):
                            try:
                                args = s.tool_args
                                if isinstance(args, str):
                                    args = json.loads(args)
                                result = self._tool_executor(s.tool_name, args)
                                self._plan_manager.set_step_result(p_id, s_id, str(result))
                                self._plan_manager.refresh_plan_status(p_id)
                                logger.info(f"Plan step executed: {s.action[:50]} → {str(result)[:100]}")
                                from x_agent_kit.channels.feishu_cards import build_step_result_card
                                self.send_card(build_step_result_card(s, str(result)))
                            except Exception as exc:
                                self._plan_manager.update_step_status(p_id, s_id, "failed")
                                self._plan_manager.set_step_result(p_id, s_id, str(exc))
                                self._plan_manager.refresh_plan_status(p_id)
                                logger.error(f"Plan step failed: {s.action[:50]} → {exc}")
                                s.status = "failed"
                                from x_agent_kit.channels.feishu_cards import build_step_result_card
                                self.send_card(build_step_result_card(s, str(exc)))
                        threading.Thread(target=execute_step, daemon=True).start()
                if decision == "reject":
                    logger.info(f"Plan step rejected: {step_id[:8]}... — no further action")
                return resp

            # --- Legacy single-action approval path ---
            request_id = value.get("request_id", "")
            if request_id and decision:
                status = "APPROVED" if decision == "approve" else "REJECTED"
                _APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
                (_APPROVAL_DIR / f"{request_id}.json").write_text(json.dumps({"status": status}), encoding="utf-8")
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
                                    card = {
                                        "schema": "2.0",
                                        "header": {"title": {"content": "✅ 执行成功", "tag": "plain_text"}, "template": "green"},
                                        "body": {"elements": [
                                            {"tag": "markdown", "content": f"**操作**: {p['action']}\n**结果**: {str(result)[:500]}"},
                                        ]},
                                    }
                                    self.send_card(card)
                                except Exception as exc:
                                    logger.error(f"Failed to execute approved action: {exc}")
                                    card = {
                                        "schema": "2.0",
                                        "header": {"title": {"content": "❌ 执行失败", "tag": "plain_text"}, "template": "red"},
                                        "body": {"elements": [
                                            {"tag": "markdown", "content": f"**操作**: {p['action']}\n**错误**: {str(exc)[:500]}"},
                                        ]},
                                    }
                                    self.send_card(card)
                            threading.Thread(target=execute, daemon=True).start()
                elif decision == "reject" and self._approval_queue:
                    self._approval_queue.resolve(request_id, "REJECTED")
        except Exception as exc:
            logger.error(f"Card callback error: {exc}")
        return resp

    def _patch_plan_step_card(self, message_id: str, decision: str, plan_id: str, step_id: str) -> None:
        """Re-render the full plan card with updated step statuses.

        Instead of replacing the entire card with a single status message,
        this rebuilds the card from PlanManager so decided steps show status
        labels while pending steps keep their approve/reject buttons.
        """
        time.sleep(0.5)
        try:
            from x_agent_kit.channels.feishu_cards import build_plan_approval_card
            plan = self._plan_manager.get(plan_id) if self._plan_manager else None
            if not plan:
                logger.error(f"Cannot patch card: plan {plan_id} not found")
                return
            card = build_plan_approval_card(plan)
            req = PatchMessageRequest.builder().message_id(message_id).request_body(
                PatchMessageRequestBody.builder().content(json.dumps(card)).build()
            ).build()
            self._client.im.v1.message.patch(req)
            logger.info(f"Plan card patched: step {step_id[:8]}... → {decision}")
        except Exception as exc:
            logger.error(f"Patch plan step card failed: {exc}")

    def _patch_card(self, message_id: str, decision: str, request_id: str) -> None:
        time.sleep(1)
        if decision == "approve":
            title = "✅ 已批准"
            color = "green"
            content = f"审批 `{request_id[:8]}...` 已批准，正在执行..."
        else:
            title = "❌ 已拒绝"
            color = "red"
            content = f"审批 `{request_id[:8]}...` 已拒绝，操作已取消。"

        card = {
            "schema": "2.0",
            "header": {"title": {"content": title, "tag": "plain_text"}, "template": color},
            "body": {"elements": [{"tag": "markdown", "content": content}]},
        }
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
