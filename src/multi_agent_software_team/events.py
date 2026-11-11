"""Presentation-neutral events emitted during mission execution."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    MISSION_STARTED = "mission_started"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    RETRY_STARTED = "retry_started"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"


@dataclass(frozen=True)
class ExecutionEvent:
    """A structured, UI-independent execution notification."""

    type: EventType
    agent: str | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    status: str | None = None
    passed: int | None = None
    failed: int | None = None
    message: str = ""


EventListener = Callable[[ExecutionEvent], Any]
