"""Tool contracts independent of model providers."""

from collections.abc import Callable
from dataclasses import dataclass

from cmf_dev_studio.tools.context import ToolContext


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[ToolContext, str], str]
    requires_exploration: bool = True


@dataclass(frozen=True)
class ToolResult:
    value: str
    cached: bool = False
    error: dict[str, str] | None = None
