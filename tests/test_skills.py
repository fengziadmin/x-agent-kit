from pathlib import Path
FIXTURES = Path(__file__).parent / "fixtures"

class TestSkillLoader:
    def _make_loader(self):
        from x_agent_kit.skills.loader import SkillLoader
        return SkillLoader(paths=[str(FIXTURES / ".agent/skills"), str(FIXTURES / "plugins")])

    def test_list_skills_finds_standalone_md(self):
        loader = self._make_loader()
        assert "my-rules" in loader.list()

    def test_list_skills_finds_directory_skill(self):
        loader = self._make_loader()
        assert "test-skill" in loader.list()

    def test_load_standalone_skill(self):
        loader = self._make_loader()
        assert "Always be polite" in loader.load("my-rules")

    def test_load_directory_skill_includes_main(self):
        loader = self._make_loader()
        assert "Main skill content" in loader.load("test-skill")

    def test_load_directory_skill_includes_references(self):
        loader = self._make_loader()
        assert "Additional knowledge" in loader.load("test-skill")

    def test_load_nonexistent_returns_not_found(self):
        loader = self._make_loader()
        assert "not found" in loader.load("nonexistent").lower()

    def test_list_returns_list_of_strings(self):
        loader = self._make_loader()
        names = loader.list()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
