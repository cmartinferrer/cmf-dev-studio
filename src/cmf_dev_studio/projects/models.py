"""Project metadata independent of CLI, web UI, and agent execution."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    description: str
    created_at: str
    language: ProjectLanguage = ProjectLanguage.AUTO

    python_interpreter: str | None = None
    python_version: str | None = None
    jdk_home: str | None = None
