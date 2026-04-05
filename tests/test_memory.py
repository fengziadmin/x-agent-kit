import json
from pathlib import Path
import pytest


class TestMemory:
    def _make_memory(self, tmp_path):
        from x_agent_kit.memory import Memory
        return Memory(memory_dir=str(tmp_path / "memory"))

    def test_save_and_load(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("test-key", "test content")
        assert mem.load("test-key") == "test content"

    def test_load_nonexistent_returns_none(self, tmp_path):
        mem = self._make_memory(tmp_path)
        assert mem.load("nonexistent") is None

    def test_load_all_returns_list(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("a", "content a")
        mem.save("b", "content b")
        entries = mem.load_all()
        assert len(entries) == 2

    def test_summary_returns_string(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("test", "some data")
        summary = mem.summary()
        assert "some data" in summary

    def test_summary_empty(self, tmp_path):
        mem = self._make_memory(tmp_path)
        assert "No previous" in mem.summary()

    def test_delete(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("to-delete", "data")
        mem.delete("to-delete")
        assert mem.load("to-delete") is None

    def test_clear(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("a", "1")
        mem.save("b", "2")
        mem.clear()
        assert len(mem.load_all()) == 0

    def test_search_finds_by_keyword(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("ads-report", "Google Ads campaign PrivideoAI had 0 conversions")
        mem.save("ga4-report", "GA4 traffic summary shows 200 sessions")
        mem.save("weather", "Today is sunny and warm")
        results = mem.search("Google Ads conversions")
        assert len(results) >= 1
        assert any("PrivideoAI" in r["content"] for r in results)

    def test_search_empty_query_returns_recent(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("a", "first")
        mem.save("b", "second")
        results = mem.search("")
        assert len(results) == 2

    def test_load_recent(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("old", "old content")
        mem.save("new", "new content")
        recent = mem.load_recent(1)
        assert len(recent) == 1

    def test_count(self, tmp_path):
        mem = self._make_memory(tmp_path)
        assert mem.count() == 0
        mem.save("a", "1")
        mem.save("b", "2")
        assert mem.count() == 2

    def test_update_existing_key(self, tmp_path):
        mem = self._make_memory(tmp_path)
        mem.save("key1", "old value")
        mem.save("key1", "new value")
        assert mem.load("key1") == "new value"
        assert mem.count() == 1

    def test_migrate_json_files(self, tmp_path):
        """Existing JSON memory files should be migrated to SQLite."""
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir(parents=True)
        # Create a JSON memory file
        json_file = mem_dir / "legacy.json"
        json_file.write_text(json.dumps({
            "key": "legacy",
            "content": "legacy content",
            "timestamp": "2026-01-01T00:00:00"
        }))
        # Initialize memory (should auto-migrate)
        from x_agent_kit.memory import Memory
        mem = Memory(memory_dir=str(mem_dir))
        assert mem.load("legacy") == "legacy content"
        assert not json_file.exists()  # JSON file should be deleted after migration
