from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from loguru import logger


class Memory:
    """Persistent memory across agent runs. Stores as JSON files in .agent/memory/."""

    def __init__(self, memory_dir: str = ".agent/memory") -> None:
        self._dir = Path(memory_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, content: str) -> None:
        """Save a memory entry."""
        entry = {
            "key": key,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        file_path = self._dir / f"{key}.json"
        file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"Memory saved: {key}")

    def load(self, key: str) -> str | None:
        """Load a specific memory entry."""
        file_path = self._dir / f"{key}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return data.get("content")
        except Exception:
            return None

    def load_all(self) -> list[dict]:
        """Load all memory entries, sorted by timestamp."""
        entries = []
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries.append(data)
            except Exception:
                continue
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries

    def summary(self, max_entries: int = 10) -> str:
        """Return a summary string of recent memories for injection into prompts."""
        entries = self.load_all()[:max_entries]
        if not entries:
            return "No previous memories."
        parts = ["## Previous Session Memories\n"]
        for e in entries:
            parts.append(f"**[{e.get('timestamp', '?')[:16]}] {e.get('key', '?')}**\n{e.get('content', '')}\n")
        return "\n".join(parts)

    def delete(self, key: str) -> None:
        """Delete a memory entry."""
        file_path = self._dir / f"{key}.json"
        if file_path.exists():
            file_path.unlink()

    def clear(self) -> None:
        """Delete all memories."""
        for f in self._dir.glob("*.json"):
            f.unlink()
