"""Filesystem output writer."""

from __future__ import annotations

from pathlib import Path


class FilesystemWriter:
    """Writes generated output files to the filesystem."""

    def write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_multiple(self, files: dict[str, str], base_dir: Path) -> list[Path]:
        written: list[Path] = []
        for filename, content in files.items():
            path = base_dir / filename
            self.write(path, content)
            written.append(path)
        return written
