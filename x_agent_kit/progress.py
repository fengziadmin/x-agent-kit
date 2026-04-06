from __future__ import annotations

from typing import Any

from x_agent_kit.i18n import t


class ProgressRenderer:
    """Encapsulates all streaming card / progress display logic."""

    def __init__(self, channel: Any = None, enabled: bool = True) -> None:
        self._card: Any = None
        self._steps: list[str] = []
        if enabled and channel and hasattr(channel, "send_streaming_start"):
            self._card = channel.send_streaming_start(t("agent.thinking"))

    def add_step(self, label: str) -> None:
        self._steps.append(f"{label}...")
        self._refresh()

    def complete_step(self, label: str) -> None:
        if self._steps:
            self._steps[-1] = f"✅ {label}"
        self._refresh()

    def update_text(self, text: str) -> None:
        if self._card:
            rendered = self._render_steps()
            self._card.update_text(rendered + "\n\n" + text if rendered else text)

    def finish(self, title: str, content: str, color: str = "green") -> None:
        if self._card:
            final = self._render_steps() + "\n---\n" + content if self._steps else content
            self._card.complete(title, final, color)

    def warn(self, title: str) -> None:
        if self._card:
            self._card.complete(title, self._render_steps(), "yellow")

    def _render_steps(self) -> str:
        return "\n".join(f"- {s}" for s in self._steps)

    def _refresh(self) -> None:
        if self._card:
            self._card.update_text(self._render_steps())
