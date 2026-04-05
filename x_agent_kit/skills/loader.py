from __future__ import annotations
from pathlib import Path
from loguru import logger

class SkillLoader:
    def __init__(self, paths: list[str]) -> None:
        self._paths = [Path(p).expanduser() for p in paths]

    def list(self) -> list[str]:
        skills = []
        for base in self._paths:
            if not base.exists():
                continue
            for md in base.glob("*.md"):
                skills.append(md.stem)
            for skill_dir in base.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append(skill_dir.name)
            for skill_md in base.rglob("SKILL.md"):
                name = skill_md.parent.name
                if name not in skills:
                    skills.append(name)
        return sorted(set(skills))

    def load(self, name: str) -> str:
        for base in self._paths:
            if not base.exists():
                continue
            standalone = base / f"{name}.md"
            if standalone.is_file():
                return standalone.read_text(encoding="utf-8")
            skill_dir = base / name
            skill_main = skill_dir / "SKILL.md"
            if skill_main.is_file():
                return self._load_directory_skill(name, skill_dir)
            for skill_md in base.rglob("SKILL.md"):
                if skill_md.parent.name == name:
                    return self._load_directory_skill(name, skill_md.parent)
        return f"Skill '{name}' not found."

    def _load_directory_skill(self, name: str, skill_dir: Path) -> str:
        parts = []
        main = skill_dir / "SKILL.md"
        if main.is_file():
            parts.append(main.read_text(encoding="utf-8"))
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            for ref in sorted(refs_dir.glob("*.md")):
                parts.append(f"\n\n---\n## Reference: {ref.stem}\n\n")
                parts.append(ref.read_text(encoding="utf-8"))
        return "".join(parts)
