import sys
from unittest.mock import patch, MagicMock

# Mock the openai module before any import of openai_brain
_mock_openai = MagicMock()
sys.modules.setdefault("openai", _mock_openai)

class TestOpenAIBrain:
    def test_think_returns_text(self):
        with patch("x_agent_kit.brain.openai_brain.openai") as mock_openai:
            from x_agent_kit.brain.openai_brain import OpenAIBrain
            from x_agent_kit.models import Message
            mock_choice = MagicMock()
            mock_choice.message.content = "hello"
            mock_choice.message.tool_calls = None
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_resp
            brain = OpenAIBrain(api_key="fake")
            result = brain.think([Message(role="user", content="hi")], tools=[])
            assert result.text == "hello"

    def test_think_returns_tool_calls(self):
        with patch("x_agent_kit.brain.openai_brain.openai") as mock_openai:
            from x_agent_kit.brain.openai_brain import OpenAIBrain
            from x_agent_kit.models import Message
            mock_tc = MagicMock()
            mock_tc.id = "call_1"
            mock_tc.function.name = "search"
            mock_tc.function.arguments = '{"q": "test"}'
            mock_choice = MagicMock()
            mock_choice.message.content = None
            mock_choice.message.tool_calls = [mock_tc]
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_resp
            brain = OpenAIBrain(api_key="fake")
            result = brain.think([Message(role="user", content="search")], tools=[{"type": "function", "function": {"name": "search", "description": "s", "parameters": {}}}])
            assert result.tool_calls[0].name == "search"
