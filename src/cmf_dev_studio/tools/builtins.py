"""Composition root for built-in tools."""

from cmf_dev_studio.tools.models import ToolDefinition
from cmf_dev_studio.tools.registry import ToolRegistry
from cmf_dev_studio.tools.repository.find import find
from cmf_dev_studio.tools.repository.read import read
from cmf_dev_studio.tools.repository.search import search


def repository_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition("find", "Find filename or glob", find))
    registry.register(ToolDefinition("search", "Search literal code text", search))
    registry.register(ToolDefinition("read", "Read exact relative path", read))
    return registry
