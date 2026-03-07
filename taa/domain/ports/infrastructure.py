"""Infrastructure port interfaces."""

from __future__ import annotations

from typing import Protocol
from pathlib import Path


class TemplateRendererPort(Protocol):
    """Port for rendering templates."""

    def render(self, template_name: str, context: dict) -> str: ...


class OutputWriterPort(Protocol):
    """Port for writing generated output to the filesystem."""

    def write(self, path: Path, content: str) -> None: ...

    def write_multiple(self, files: dict[str, str], base_dir: Path) -> list[Path]: ...
