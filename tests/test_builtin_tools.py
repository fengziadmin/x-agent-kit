from pathlib import Path
from unittest.mock import MagicMock
FIXTURES = Path(__file__).parent / "fixtures"

class TestBuiltinLoadSkill:
    def test_load_skill_returns_content(self):
        from x_agent_kit.tools.builtin import create_load_skill_tool
        from x_agent_kit.skills.loader import SkillLoader
        loader = SkillLoader(paths=[str(FIXTURES / ".agent/skills")])
        fn = create_load_skill_tool(loader)
        result = fn(name="my-rules")
        assert "Always be polite" in result

    def test_load_skill_not_found(self):
        from x_agent_kit.tools.builtin import create_load_skill_tool
        from x_agent_kit.skills.loader import SkillLoader
        loader = SkillLoader(paths=[str(FIXTURES / ".agent/skills")])
        fn = create_load_skill_tool(loader)
        result = fn(name="nonexistent")
        assert "not found" in result.lower()

class TestBuiltinListSkills:
    def test_list_skills_returns_names(self):
        from x_agent_kit.tools.builtin import create_list_skills_tool
        from x_agent_kit.skills.loader import SkillLoader
        loader = SkillLoader(paths=[str(FIXTURES / ".agent/skills")])
        fn = create_list_skills_tool(loader)
        result = fn()
        assert "my-rules" in result

class TestBuiltinNotify:
    def test_notify_calls_channel(self):
        from x_agent_kit.tools.builtin import create_notify_tool
        mock_channels = {"default": MagicMock()}
        mock_channels["default"].send_text.return_value = {"ok": True}
        fn = create_notify_tool(mock_channels)
        result = fn(message="hello")
        assert result is True
        mock_channels["default"].send_text.assert_called_once_with("hello")

class TestBuiltinRequestApproval:
    def test_request_approval_calls_channel(self):
        from x_agent_kit.tools.builtin import create_request_approval_tool
        mock_channels = {"default": MagicMock()}
        mock_channels["default"].request_approval.return_value = "APPROVED"
        fn = create_request_approval_tool(mock_channels)
        result = fn(action="test", details="detail")
        assert result == "APPROVED"
