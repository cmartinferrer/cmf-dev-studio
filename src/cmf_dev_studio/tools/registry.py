"""Explicit registry of trusted tool implementations."""

from cmf_dev_studio.tools.models import ToolDefinition


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        if not tool.name.strip() or tool.name in self._tools:
            raise ValueError("Invalid or duplicate tool name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        return self._tools[name]

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())
