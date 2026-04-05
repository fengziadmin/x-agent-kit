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
