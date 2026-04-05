from __future__ import annotations
import json
from unittest.mock import MagicMock, patch

class TestFeishuMessageHandler:
    def _make_feishu_channel(self):
        with patch("x_agent_kit.channels.feishu.lark") as mock_lark:
            mock_client = MagicMock()
            mock_lark.Client.builder.return_value.app_id.return_value.app_secret.return_value.log_level.return_value.build.return_value = mock_client
            from x_agent_kit.channels.feishu import FeishuChannel
            ch = FeishuChannel("app_id", "secret", "chat_id")
            ch._client = mock_client
            return ch

    def test_set_message_handler(self):
        ch = self._make_feishu_channel()
        handler = MagicMock()
        ch.set_message_handler(handler)
        assert ch._message_handler is handler

    def test_on_message_receive_calls_handler(self):
        ch = self._make_feishu_channel()
        handler = MagicMock()
        ch.set_message_handler(handler)
        event = MagicMock()
        event.event.message.chat_id = "chat-123"
        event.event.message.message_type = "text"
        event.event.message.content = json.dumps({"text": "查一下 Campaign A 表现"})
        event.event.sender.sender_type = "user"
        ch._on_message_receive(event)
        handler.assert_called_once_with("chat-123", "查一下 Campaign A 表现")

    def test_ignores_bot_own_messages(self):
        ch = self._make_feishu_channel()
        handler = MagicMock()
        ch.set_message_handler(handler)
        event = MagicMock()
        event.event.message.chat_id = "chat-123"
        event.event.message.message_type = "text"
        event.event.message.content = json.dumps({"text": "hello"})
        event.event.sender.sender_type = "app"
        ch._on_message_receive(event)
        handler.assert_not_called()
