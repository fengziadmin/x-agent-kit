from pathlib import Path
from unittest.mock import MagicMock, patch
FIXTURES = Path(__file__).parent / "fixtures"

class TestIntegration:
    def test_agent_uses_tool_and_skill(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        from x_agent_kit.tools.base import tool

        @tool("echo back the input")
        def echo(text: str) -> str:
            return f"echo: {text}"

        responses = [
            BrainResponse(tool_calls=[ToolCall(id="1", name="list_skills", arguments={})]),
            BrainResponse(tool_calls=[ToolCall(id="2", name="load_skill", arguments={"name": "my-rules"})]),
            BrainResponse(tool_calls=[ToolCall(id="3", name="echo", arguments={"text": "polite"})]),
            BrainResponse(text="Done. The skill says be polite, echo confirmed.", done=True),
        ]
        mock_brain = MagicMock()
        mock_brain.think = MagicMock(side_effect=responses)
        with patch("x_agent_kit.agent.load_config") as mock_config, \
             patch("x_agent_kit.agent.create_brain", return_value=mock_brain):
            mock_config.return_value = MagicMock(
                brain=MagicMock(provider="gemini"),
                providers={"gemini": MagicMock(type="api", resolve_api_key=lambda: "key")},
                channels={"default": "cli"},
                skills=MagicMock(paths=[str(FIXTURES / ".agent/skills")]),
                agent=MagicMock(max_iterations=50),
            )
            from x_agent_kit.agent import Agent
            agent = Agent(config_dir=str(FIXTURES / ".agent"))
            agent.register_tools([echo])
            result = agent.run("test task")
        assert "polite" in result
        assert mock_brain.think.call_count == 4
