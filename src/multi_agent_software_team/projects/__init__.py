"""Persistent local project registry for Multi-Agent Studio."""

from .manager import ProjectManager
from .models import Project, ProjectKind

__all__ = ["Project", "ProjectKind", "ProjectManager"]
