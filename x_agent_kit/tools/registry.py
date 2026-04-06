from __future__ import annotations
from typing import Any, Callable
from loguru import logger
from x_agent_kit.tools.base import ToolMeta

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolMeta] = {}

    def register(self, func: Callable) -> None:
        meta: ToolMeta = getattr(func, "_tool_meta", None)
        if meta is None:
            raise ValueError(f"{func.__name__} is not decorated with @tool")
        self._tools[meta.name] = meta

    def list(self) -> list[ToolMeta]:
        return list(self._tools.values())

    def get_meta(self, name: str) -> ToolMeta | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [meta.schema() for meta in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        meta = self._tools[name]
        try:
            return meta.func(**arguments)
        except Exception as exc:
            error_msg = f"Tool '{name}' failed: {type(exc).__name__}: {exc}"
            logger.error(error_msg)
            return error_msg
