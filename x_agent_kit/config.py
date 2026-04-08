"""Configuration loader for x-agent-kit.

Priority (highest to lowest):
1. Environment variables (XAGENT_* prefix)
2. settings.json file (if exists)
3. Defaults

Environment variable mapping:
  XAGENT_BRAIN_PROVIDER    = openai | gemini | claude
  XAGENT_BRAIN_MODEL       = gpt-4o | gemini-2.0-flash | etc.
  XAGENT_MAX_ITERATIONS    = 50
  XAGENT_APPROVAL_TIMEOUT  = 3600
  XAGENT_MEMORY_ENABLED    = true | false
  XAGENT_MEMORY_DIR        = data/agent_memory
  XAGENT_SKILLS_DIR        = src/skills (comma-separated for multiple)
  XAGENT_CHANNEL_DEFAULT   = cli | feishu
  XAGENT_LOCALE            = zh_CN | en_US

  Provider API keys (standard names, no prefix):
  OPENAI_API_KEY           = sk-...
  GEMINI_API_KEY           = ...
  ANTHROPIC_API_KEY        = sk-ant-api03-...

  Feishu channel (standard names):
  LARK_APP_ID              = cli_...
  LARK_APP_SECRET          = ...
  LARK_CHAT_ID             = oc_...
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


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
    system_prompt: str = ""
    schedules: list[ScheduleConfig] = field(default_factory=list)
    locale: str = "zh_CN"


def _env(key: str, default: str = "") -> str:
    """Read an environment variable."""
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    val = os.environ.get(key, "")
    if not val:
        return default
    return val.lower() in ("true", "1", "yes")


def _env_int(key: str, default: int = 0) -> int:
    """Read an integer environment variable."""
    val = os.environ.get(key, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _build_providers_from_env() -> dict[str, ProviderConfig]:
    """Auto-detect providers from environment variables."""
    providers = {}

    if _env("OPENAI_API_KEY"):
        providers["openai"] = ProviderConfig(
            type="api",
            api_key_env="OPENAI_API_KEY",
            default_model=_env("XAGENT_OPENAI_MODEL", "gpt-4o"),
        )

    if _env("GEMINI_API_KEY"):
        providers["gemini"] = ProviderConfig(
            type="api",
            api_key_env="GEMINI_API_KEY",
            default_model=_env("XAGENT_GEMINI_MODEL", "gemini-2.0-flash"),
        )

    # Claude CLI — always available (uses CLAUDE_CODE_OAUTH_TOKEN or local auth)
    providers["claude"] = ProviderConfig(type="cli")

    return providers


def _build_channels_from_env() -> dict[str, Any]:
    """Auto-detect channels from environment variables."""
    channels: dict[str, Any] = {"default": _env("XAGENT_CHANNEL_DEFAULT", "cli")}

    if _env("LARK_APP_ID") and _env("LARK_APP_SECRET"):
        channels["feishu"] = {
            "app_id_env": "LARK_APP_ID",
            "app_secret_env": "LARK_APP_SECRET",
            "default_chat_id_env": "LARK_CHAT_ID",
        }
        # Auto-switch default to feishu if configured
        if channels["default"] == "cli":
            channels["default"] = "feishu"

    return channels


def _load_identity(config_dir: str = ".agent") -> str:
    """Load IDENTITY.md + SOUL.md + AGENTS.md from the active identity directory.

    Reads XAGENT_IDENTITY env var to select which identity to load from
    ``{config_dir}/identities/{identity}/``. Falls back to the first
    identity found if env var is not set.

    Returns concatenated content, or empty string if no identity files found.
    """
    identity_name = _env("XAGENT_IDENTITY", "")
    base = Path(config_dir) / "identities"

    if not base.exists():
        return ""

    # Resolve identity directory
    if identity_name:
        identity_dir = base / identity_name
    else:
        # Auto-detect: use first directory that has at least one .md file
        identity_dir = None
        for d in sorted(base.iterdir()):
            if d.is_dir() and any(d.glob("*.md")):
                identity_dir = d
                break
        if identity_dir is None:
            return ""

    if not identity_dir.exists():
        logger.warning(f"Identity directory not found: {identity_dir}")
        return ""

    # Load in order: IDENTITY → SOUL → AGENTS
    parts = []
    for filename in ["IDENTITY.md", "SOUL.md", "AGENTS.md"]:
        filepath = identity_dir / filename
        if filepath.is_file():
            parts.append(filepath.read_text(encoding="utf-8").strip())

    if parts:
        logger.info(f"Loaded identity: {identity_dir.name} ({len(parts)} files)")

    return "\n\n".join(parts)


def _load_from_env() -> Config:
    """Build Config entirely from environment variables."""
    provider_name = _env("XAGENT_BRAIN_PROVIDER", "openai")
    providers = _build_providers_from_env()

    # If specified provider not in auto-detected, still add it
    if provider_name not in providers:
        if provider_name == "claude":
            providers["claude"] = ProviderConfig(type="cli")
        else:
            providers[provider_name] = ProviderConfig(
                type="api",
                api_key_env=f"{provider_name.upper()}_API_KEY",
            )

    skills_dir = _env("XAGENT_SKILLS_DIR", ".agent/skills")
    skills_paths = [p.strip() for p in skills_dir.split(",") if p.strip()]

    return Config(
        brain=BrainConfig(
            provider=provider_name,
            model=_env("XAGENT_BRAIN_MODEL", ""),
        ),
        providers=providers,
        channels=_build_channels_from_env(),
        skills=SkillsConfig(paths=skills_paths),
        agent=AgentConfig(
            max_iterations=_env_int("XAGENT_MAX_ITERATIONS", 50),
            approval_timeout=_env_int("XAGENT_APPROVAL_TIMEOUT", 3600),
        ),
        memory=MemoryConfig(
            enabled=_env_bool("XAGENT_MEMORY_ENABLED", True),
            dir=_env("XAGENT_MEMORY_DIR", ".agent/memory"),
        ),
        system_prompt=_load_identity(".agent"),
        locale=_env("XAGENT_LOCALE", "zh_CN"),
    )


def _load_from_file(config_dir: str) -> Config:
    """Load Config from settings.json file (original behavior)."""
    config_path = Path(config_dir) / "settings.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    brain = BrainConfig(**raw.get("brain", {}))
    providers = {}
    for name, prov in raw.get("providers", {}).items():
        providers[name] = ProviderConfig(**prov)
    channels = raw.get("channels", {"default": "cli"})
    skills_raw = raw.get("skills", {})

    # Support both "dir" (single) and "paths" (list)
    if "dir" in skills_raw:
        skills = SkillsConfig(paths=[skills_raw["dir"]])
    else:
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

    locale = raw.get("locale", raw.get("language", "zh_CN"))

    return Config(
        brain=brain,
        providers=providers,
        channels=channels,
        skills=skills,
        agent=agent,
        memory=memory,
        system_prompt=_load_identity(config_dir),
        schedules=schedules,
        locale=locale,
    )


def _merge_env_overrides(config: Config) -> Config:
    """Override settings.json values with environment variables (if set)."""
    # Brain
    env_provider = _env("XAGENT_BRAIN_PROVIDER")
    if env_provider:
        config.brain.provider = env_provider
    env_model = _env("XAGENT_BRAIN_MODEL")
    if env_model:
        config.brain.model = env_model

    # Agent
    env_max_iter = _env("XAGENT_MAX_ITERATIONS")
    if env_max_iter:
        config.agent.max_iterations = int(env_max_iter)

    # Memory
    env_memory = _env("XAGENT_MEMORY_ENABLED")
    if env_memory:
        config.memory.enabled = env_memory.lower() in ("true", "1", "yes")
    env_memory_dir = _env("XAGENT_MEMORY_DIR")
    if env_memory_dir:
        config.memory.dir = env_memory_dir

    # Skills
    env_skills = _env("XAGENT_SKILLS_DIR")
    if env_skills:
        config.skills.paths = [p.strip() for p in env_skills.split(",") if p.strip()]

    # Channel default
    env_channel = _env("XAGENT_CHANNEL_DEFAULT")
    if env_channel:
        config.channels["default"] = env_channel

    # Auto-add providers from env if not in file
    if _env("OPENAI_API_KEY") and "openai" not in config.providers:
        config.providers["openai"] = ProviderConfig(
            type="api", api_key_env="OPENAI_API_KEY", default_model="gpt-4o",
        )
    if _env("GEMINI_API_KEY") and "gemini" not in config.providers:
        config.providers["gemini"] = ProviderConfig(
            type="api", api_key_env="GEMINI_API_KEY", default_model="gemini-2.0-flash",
        )
    if "claude" not in config.providers:
        config.providers["claude"] = ProviderConfig(type="cli")

    # Auto-add feishu channel from env if not in file
    if _env("LARK_APP_ID") and _env("LARK_APP_SECRET"):
        if "feishu" not in config.channels:
            config.channels["feishu"] = {
                "app_id_env": "LARK_APP_ID",
                "app_secret_env": "LARK_APP_SECRET",
                "default_chat_id_env": "LARK_CHAT_ID",
            }

    # Locale
    env_locale = _env("XAGENT_LOCALE")
    if env_locale:
        config.locale = env_locale

    return config


def load_config(config_dir: str = ".agent") -> Config:
    """Load configuration with priority: env vars > settings.json > defaults.

    If settings.json exists, loads it first then applies env var overrides.
    If settings.json doesn't exist, builds config entirely from env vars.
    """
    config_path = Path(config_dir) / "settings.json"

    if config_path.exists():
        logger.debug(f"Loading config from {config_path}")
        config = _load_from_file(config_dir)
        config = _merge_env_overrides(config)
    else:
        logger.debug("No settings.json found, loading config from environment variables")
        config = _load_from_env()

    logger.debug(f"Config: brain={config.brain.provider}/{config.brain.model}, "
                 f"channel={config.channels.get('default', 'cli')}")
    return config
