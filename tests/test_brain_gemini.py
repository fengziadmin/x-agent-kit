from unittest.mock import MagicMock, patch

class TestGeminiBrain:
    def _make_brain(self):
        with patch("x_agent_kit.brain.gemini.genai") as mock_genai:
            from x_agent_kit.brain.gemini import GeminiBrain
            brain = GeminiBrain(api_key="fake-key", model="gemini-2.5-flash")
            return brain

    def test_think_returns_brain_response(self):
        from x_agent_kit.models import Message, BrainResponse
        brain = self._make_brain()
        mock_resp = MagicMock()
        mock_resp.candidates = [MagicMock()]
        mock_resp.candidates[0].content.parts = [MagicMock(text="hello", function_call=None)]
        brain._client.models.generate_content.return_value = mock_resp
        result = brain.think(messages=[Message(role="user", content="hi")], tools=[])
        assert isinstance(result, BrainResponse)
        assert result.text == "hello"

    def test_think_returns_tool_calls(self):
        from x_agent_kit.models import Message
        brain = self._make_brain()
        mock_fc = MagicMock()
        mock_fc.name = "search"
        mock_fc.args = {"q": "test"}
        mock_part = MagicMock(text=None, function_call=mock_fc)
        mock_resp = MagicMock()
        mock_resp.candidates = [MagicMock()]
        mock_resp.candidates[0].content.parts = [mock_part]
        brain._client.models.generate_content.return_value = mock_resp
        result = brain.think(messages=[Message(role="user", content="search")], tools=[{"type": "function", "function": {"name": "search", "description": "s", "parameters": {}}}])
        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "search"

    def test_think_with_empty_response(self):
        from x_agent_kit.models import Message
        brain = self._make_brain()
        mock_resp = MagicMock()
        mock_resp.candidates = []
        brain._client.models.generate_content.return_value = mock_resp
        result = brain.think(messages=[Message(role="user", content="hi")], tools=[])
        assert result.text == ""
