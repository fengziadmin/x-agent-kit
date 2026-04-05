from unittest.mock import patch, MagicMock

class TestCLIChannel:
    def test_send_text_prints(self, capsys):
        from x_agent_kit.channels.cli_channel import CLIChannel
        ch = CLIChannel()
        ch.send_text("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_send_card_prints_formatted(self, capsys):
        from x_agent_kit.channels.cli_channel import CLIChannel
        ch = CLIChannel()
        ch.send_card({"title": "Report", "body": "data"})
        captured = capsys.readouterr()
        assert "Report" in captured.out

    def test_request_approval_returns_approved(self):
        from x_agent_kit.channels.cli_channel import CLIChannel
        ch = CLIChannel()
        with patch("builtins.input", return_value="y"):
            result = ch.request_approval("change budget", "increase by 20%")
        assert result == "APPROVED"

    def test_request_approval_returns_rejected(self):
        from x_agent_kit.channels.cli_channel import CLIChannel
        ch = CLIChannel()
        with patch("builtins.input", return_value="n"):
            result = ch.request_approval("change budget", "increase by 20%")
        assert result == "REJECTED"

class TestFeishuChannel:
    def test_send_text_calls_sdk(self):
        with patch("x_agent_kit.channels.feishu.lark") as mock_lark:
            mock_builder = MagicMock()
            mock_builder.app_id.return_value = mock_builder
            mock_builder.app_secret.return_value = mock_builder
            mock_builder.log_level.return_value = mock_builder
            mock_client = MagicMock()
            mock_builder.build.return_value = mock_client
            mock_lark.Client.builder.return_value = mock_builder
            mock_resp = MagicMock()
            mock_resp.success.return_value = True
            mock_resp.data.message_id = "om_123"
            mock_client.im.v1.message.create.return_value = mock_resp
            from x_agent_kit.channels.feishu import FeishuChannel
            ch = FeishuChannel(app_id="id", app_secret="secret", chat_id="oc_test")
            result = ch.send_text("hello")
            assert result.get("ok") is True
