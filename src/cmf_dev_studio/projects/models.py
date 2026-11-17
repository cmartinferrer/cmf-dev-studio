"""Project metadata independent of CLI, web UI, and agent execution."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ProjectKind(str, Enum):
    MANAGED = "managed"
    EXISTING = "existing"


class ProjectLanguage(str, Enum):
    AUTO = "auto"
    PYTHON = "python"
    JAVA = "java"
    KOTLIN = "kotlin"


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: Path
    kind: ProjectKind
    description: str
    created_at: str
    language: ProjectLanguage = ProjectLanguage.AUTO

    python_interpreter: str | None = None
    python_version: str | None = None

    @property
    def read_only(self) -> bool:
        """Existing repositories are registered but never edited by this layer."""
        return self.kind is ProjectKind.EXISTING
