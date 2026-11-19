"""Central authorization, validation and dispatch."""

import logging

from cmf_dev_studio.tools.context import ToolContext
from cmf_dev_studio.tools.models import ToolResult
from cmf_dev_studio.tools.registry import ToolRegistry

LOGGER = logging.getLogger("uvicorn.error.cmf.tools")


class ToolRequestError(ValueError):
    """A rejected model request, distinct from a tool implementation failure."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, context: ToolContext, name: str, query: str) -> ToolResult:
        try:
            tool = self.registry.get(name)
        except ValueError as exc:
            raise ToolRequestError("unknown_tool", "Unknown tool") from exc
        if tool.requires_exploration and not context.allowed:
            raise ToolRequestError(
                "permission_required", "Exploration permission required"
            )
        if not isinstance(query, str) or not query.strip() or len(query) > 300:
            raise ToolRequestError(
                "invalid_query",
                "Invalid investigation tool request: query must contain 1 to 300 characters",
            )
        key = (name, query)
        if key in context.cache:
            return ToolResult(context.cache[key], cached=True)
        LOGGER.info("Executing tool: %s", tool.name)
        result = tool.handler(context, query)
        context.cache[key] = result
        context.activity(name, query)
        return ToolResult(result)

    def execute_recoverable(
        self, context: ToolContext, name: str, query: str
    ) -> ToolResult:
        """Return validation errors as data; propagate unexpected failures."""
        try:
            return self.execute(context, name, query)
        except ToolRequestError as exc:
            LOGGER.warning("Tool request rejected: %s", exc.code)
            return ToolResult("", error={"code": exc.code, "message": str(exc)})
