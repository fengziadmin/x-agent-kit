from unittest.mock import MagicMock, patch
from pathlib import Path
FIXTURES = Path(__file__).parent / "fixtures"


class TestAgentRun:
    def _make_agent(self, brain_responses, stop_condition=None):
        from x_agent_kit.agent import Agent
        mock_brain = MagicMock()
        mock_brain.think = MagicMock(side_effect=brain_responses)
        with patch("x_agent_kit.agent.load_config") as mock_config, \
             patch("x_agent_kit.agent.create_brain", return_value=mock_brain):
            mock_config.return_value = MagicMock(
                brain=MagicMock(provider="gemini"),
                providers={"gemini": MagicMock(type="api", resolve_api_key=lambda: "key")},
                channels={"default": "cli"},
                skills=MagicMock(paths=[str(FIXTURES / ".agent/skills")]),
                agent=MagicMock(max_iterations=50),
                memory=MagicMock(enabled=False),
                locale="zh_CN",
            )
            agent = Agent(config_dir=str(FIXTURES / ".agent"), stop_condition=stop_condition)
            return agent

    def test_run_returns_text_when_done(self):
        from x_agent_kit.models import BrainResponse
        agent = self._make_agent([BrainResponse(text="task complete", done=True)])
        assert agent.run("do something") == "task complete"

    def test_run_executes_tool_calls(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        from x_agent_kit.tools.base import tool
        @tool("adds numbers", label="➕ Add")
        def add(a: int, b: int) -> int:
            return a + b
        agent = self._make_agent([
            BrainResponse(tool_calls=[ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})]),
            BrainResponse(text="result is 5", done=True),
        ])
        agent.register_tools([add])
        assert "5" in agent.run("add 2+3")

    def test_run_stops_at_max_iterations(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        responses = [BrainResponse(tool_calls=[ToolCall(id="1", name="list_skills", arguments={})])] * 5
        agent = self._make_agent(responses)
        agent._config.agent.max_iterations = 3
        assert "max iterations" in agent.run("loop").lower()

    def test_run_text_without_tool_calls_completes(self):
        from x_agent_kit.models import BrainResponse
        agent = self._make_agent([BrainResponse(text="answer")])
        assert agent.run("question") == "answer"

    def test_stop_condition_terminates_loop(self):
        from x_agent_kit.models import BrainResponse, ToolCall
        from x_agent_kit.tools.base import tool
        @tool("saves", label="💾 Save")
        def save_memory(key: str, content: str) -> str:
            return "saved"
        agent = self._make_agent(
            [
                BrainResponse(tool_calls=[ToolCall(id="1", name="save_memory", arguments={"key": "k", "content": "v"})]),
                BrainResponse(text="should not reach here", done=True),
            ],
            stop_condition=lambda name, _: name == "save_memory",
        )
        agent.register_tools([save_memory])
        result = agent.run("save something")
        assert result != "should not reach here"

    def test_no_tool_labels_dict_in_agent(self):
        import inspect
        from x_agent_kit import agent as agent_module
        source = inspect.getsource(agent_module)
        assert "query_campaigns" not in source
        assert "query_ga4_traffic" not in source
        assert "query_campaign_ga4" not in source
        assert "analyze_website" not in source

    def test_no_memory_saved_in_agent(self):
        import inspect
        from x_agent_kit import agent as agent_module
        source = inspect.getsource(agent_module)
        assert "memory_saved" not in source
