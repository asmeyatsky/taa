"""Application settings."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Settings:
    """TAA application settings."""

    project_id: str = "telco-analytics"
    default_jurisdiction: str = "SA"
    default_region: str = "me-central1"
    output_dir: str = "./output"
