from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BrainConfig:
    provider: str
    model: str = ""


@dataclass
class ProviderConfig:
    type: str  # "api" | "cli"
    api_key_env: str = ""
    default_model: str = ""

    def resolve_api_key(self) -> str:
        if not self.api_key_env:
            return ""
        return os.environ.get(self.api_key_env, "")


@dataclass
class SkillsConfig:
    paths: list[str] = field(default_factory=lambda: [".agent/skills"])


@dataclass
class AgentConfig:
    max_iterations: int = 50
    approval_timeout: int = 3600


@dataclass
class MemoryConfig:
    enabled: bool = True
    dir: str = ".agent/memory"


@dataclass
class ScheduleConfig:
    cron: str
    task: str


@dataclass
class Config:
    brain: BrainConfig
    providers: dict[str, ProviderConfig]
    channels: dict[str, Any]
    skills: SkillsConfig
    agent: AgentConfig
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    schedules: list[ScheduleConfig] = field(default_factory=list)
    locale: str = "zh_CN"


def load_config(config_dir: str) -> Config:
    config_path = Path(config_dir) / "settings.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    brain = BrainConfig(**raw.get("brain", {}))
    providers = {}
    for name, prov in raw.get("providers", {}).items():
        providers[name] = ProviderConfig(**prov)
    channels = raw.get("channels", {"default": "cli"})
    skills_raw = raw.get("skills", {})
    skills = SkillsConfig(paths=skills_raw.get("paths", [".agent/skills"]))
    agent_raw = raw.get("agent", {})
    agent = AgentConfig(**agent_raw)

    memory_raw = raw.get("memory", {})
    memory = MemoryConfig(
        enabled=memory_raw.get("enabled", True),
        dir=memory_raw.get("dir", ".agent/memory"),
    )

    schedules = []
    for s in raw.get("schedules", []):
        schedules.append(ScheduleConfig(cron=s["cron"], task=s["task"]))

    locale = raw.get("locale", "zh_CN")

    return Config(
        brain=brain,
        providers=providers,
        channels=channels,
        skills=skills,
        agent=agent,
        memory=memory,
        schedules=schedules,
        locale=locale,
    )
