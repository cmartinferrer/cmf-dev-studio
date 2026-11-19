"""Regression tests for registered repository tools."""

import json

import pytest

from cmf_dev_studio.tools.builtins import repository_registry
from cmf_dev_studio.tools.context import ToolContext
from cmf_dev_studio.tools.executor import ToolExecutor
from cmf_dev_studio.tools.models import ToolDefinition
from cmf_dev_studio.tools.repository.snapshot import RepositorySnapshot


def make_context(allowed=True):
    events = []
    snapshot = RepositorySnapshot({"a.py": b"hello", ".env": b"SECRET=abc"})
    return ToolContext(snapshot, {}, allowed, lambda *args: events.append(args)), events


def test_registered_tools():
    """Dispatch existing tools and preserve their results and activity."""
    context, events = make_context()
    executor = ToolExecutor(repository_registry())
    assert json.loads(executor.execute(context, "find", "*.py").value) == ["a.py"]
    assert json.loads(executor.execute(context, "search", "hello").value) == ["a.py:1"]
    assert executor.execute(context, "read", "a.py").value == "hello"
    assert context.approved == {"a.py": "hello"}
    assert context.spent == 5
    assert executor.execute(context, "read", "a.py").cached
    assert len(events) == 3


def test_permission_before_cache():
    """A cached result cannot bypass revoked exploration permission."""
    context, _ = make_context()
    executor = ToolExecutor(repository_registry())
    executor.execute(context, "read", "a.py")
    context.allowed = False
    with pytest.raises(ValueError, match="permission"):
        executor.execute(context, "read", "a.py")


def test_unknown_and_invalid_tools():
    """Reject unknown actions and invalid arguments explicitly."""
    context, _ = make_context()
    executor = ToolExecutor(repository_registry())
    with pytest.raises(ValueError, match="Unknown tool"):
        executor.execute(context, "unknown", "hello")
    with pytest.raises(ValueError, match="Invalid investigation"):
        executor.execute(context, "read", " ")


def test_sensitive_and_budget():
    """Keep exclusions and the existing read budget."""
    context, _ = make_context()
    executor = ToolExecutor(repository_registry())
    assert (
        executor.execute(context, "read", ".env").value
        == "File unavailable or excluded."
    )
    context.spent = 48000
    assert executor.execute(context, "read", "a.py").value == "Read budget exhausted."
    assert not context.approved


def test_extension():
    """Register a new tool without changing the executor."""
    registry = repository_registry()
    tool = ToolDefinition("echo", "Echo query", lambda context, query: query)
    registry.register(tool)
    context, _ = make_context()
    assert ToolExecutor(registry).execute(context, "echo", "hello").value == "hello"
    assert tool in registry.definitions()
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(tool)


def test_recoverable_errors_preserve_permissions(caplog):
    """Reject invalid calls without dispatching or logging arguments."""
    context, events = make_context(False)
    executor = ToolExecutor(repository_registry())
    result = executor.execute_recoverable(context, "read", "private-query")
    assert result.error["code"] == "permission_required"
    assert not context.approved and not events
    assert "private-query" not in caplog.text
    context.allowed = True
    result = executor.execute_recoverable(context, "read", " ")
    assert result.error["code"] == "invalid_query"


def test_recoverable_does_not_swallow_handler_errors():
    """Unexpected handler failures still propagate."""

    def broken(context, query):
        raise ValueError("unexpected failure")

    registry = repository_registry()
    registry.register(ToolDefinition("broken", "Broken tool", broken))
    context, _ = make_context()
    with pytest.raises(ValueError, match="unexpected failure"):
        ToolExecutor(registry).execute_recoverable(context, "broken", "x")
