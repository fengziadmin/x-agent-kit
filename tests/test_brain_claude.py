from unittest.mock import patch, MagicMock

class TestClaudeBrain:
    def test_think_returns_text(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"text": "hello", "tool_calls": null, "done": false}'
        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert result.text is not None

    def test_think_handles_cli_error(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert result.text is not None
