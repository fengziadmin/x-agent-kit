import subprocess
from unittest.mock import patch, MagicMock


class TestClaudeBrain:
    def test_first_think_uses_session_id(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"{\\"text\\": \\"hello\\", \\"done\\": true}"}'

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            brain = ClaudeBrain()
            brain.think([Message(role="user", content="hi")], tools=[])
            cmd = mock_run.call_args[0][0]
            assert "--session-id" in cmd

    def test_second_think_uses_resume(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"{\\"text\\": \\"hello\\"}"}'

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            brain = ClaudeBrain()
            brain.think([Message(role="user", content="hi")], tools=[])
            brain.think([Message(role="user", content="again")], tools=[])
            second_cmd = mock_run.call_args_list[1][0][0]
            assert "--resume" in second_cmd

    def test_think_returns_text(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"{\\"text\\": \\"hello\\", \\"done\\": true}"}'

        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert result.text == "hello"

    def test_think_returns_tool_calls(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"{\\"tool_calls\\": [{\\"name\\": \\"search\\", \\"arguments\\": {\\"q\\": \\"test\\"}}]}"}'

        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="search")], tools=[{
                "type": "function",
                "function": {"name": "search", "description": "s", "parameters": {"properties": {"q": {"type": "string"}}}}
            }])
            assert result.tool_calls is not None
            assert result.tool_calls[0].name == "search"

    def test_think_handles_cli_error(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert "error" in result.text.lower()

    def test_think_handles_timeout(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)):
            brain = ClaudeBrain(timeout=300)
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert "timeout" in result.text.lower()

    def test_think_handles_plain_text_response(self):
        from x_agent_kit.brain.claude import ClaudeBrain
        from x_agent_kit.models import Message

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"just plain text answer"}'

        with patch("subprocess.run", return_value=mock_result):
            brain = ClaudeBrain()
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert "plain text" in result.text
