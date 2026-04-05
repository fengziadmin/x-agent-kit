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

_APPROVAL_DIR = Path("/tmp/x-agent-approvals")

class FeishuChannel(BaseChannel):
    def __init__(self, app_id: str, app_secret: str, chat_id: str) -> None:
        self._chat_id = chat_id
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = lark.Client.builder().app_id(app_id).app_secret(app_secret).log_level(lark.LogLevel.ERROR).build()
        self._ws_started = False

    def send_text(self, text: str) -> dict[str, Any]:
        return self._send("text", json.dumps({"text": text}))

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
        except Exception as exc:
            logger.error(f"Card callback error: {exc}")
        return resp

    def _patch_card(self, message_id: str, decision: str, request_id: str) -> None:
        time.sleep(1)
        label = "Approved" if decision == "approve" else "Rejected"
        color = "green" if decision == "approve" else "red"
        card = json.dumps({"schema": "2.0", "header": {"title": {"content": label, "tag": "plain_text"}, "template": color}, "body": {"elements": [{"tag": "markdown", "content": f"{label}: {request_id[:8]}..."}]}})
        try:
            req = PatchMessageRequest.builder().message_id(message_id).request_body(PatchMessageRequestBody.builder().content(card).build()).build()
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
