import os
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadConfig:
    def test_loads_brain_provider(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert config.brain.provider == "gemini"

    def test_loads_brain_model(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert config.brain.model == "gemini-2.5-flash"

    def test_loads_providers(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert "gemini" in config.providers
        assert config.providers["gemini"].type == "api"

    def test_loads_channels_default(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert config.channels["default"] == "cli"

    def test_loads_skills_paths(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert ".agent/skills" in config.skills.paths

    def test_loads_agent_max_iterations(self):
        from x_agent_kit.config import load_config
        config = load_config(str(FIXTURES / ".agent"))
        assert config.agent.max_iterations == 50

    def test_missing_dir_raises(self):
        import pytest
        from x_agent_kit.config import load_config
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path")

    def test_resolves_env_var(self):
        from x_agent_kit.config import load_config
        os.environ["GOOGLE_API_KEY"] = "test-key-123"
        config = load_config(str(FIXTURES / ".agent"))
        assert config.providers["gemini"].resolve_api_key() == "test-key-123"
        del os.environ["GOOGLE_API_KEY"]
