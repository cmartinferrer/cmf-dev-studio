"""Persistent local project registry for CMF Dev Studio."""

from .manager import ProjectManager
from .models import Project, ProjectKind

__all__ = ["Project", "ProjectKind", "ProjectManager"]
