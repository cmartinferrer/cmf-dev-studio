"""Shared mission state and execution history models."""

from dataclasses import dataclass, field
from enum import Enum

from multi_agent_software_team.runner.models import TestStatus


class MissionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionAttempt:
    """Snapshot of one completed test-runner invocation.

    Attributes:
        number: One-based execution attempt number.
        code: Exact implementation submitted to the runner.
        status: Classification returned by the runner.
        exit_code: Process exit code reported by the runner.
        stdout: Captured standard output.
        stderr: Captured standard error.
    """

    number: int
    code: str
    status: TestStatus
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class Mission:
    description: str
    status: MissionStatus = MissionStatus.PENDING
    requirements: list[str] = field(default_factory=list)
    code: str = ""
    tests: str = ""
    feedback: str = ""
    attempts: int = 0
    history: list[ExecutionAttempt] = field(default_factory=list)