"""Results returned by the test execution backend."""

from dataclasses import dataclass
from enum import Enum


class TestStatus(str, Enum):
    """Distinguish pytest outcomes from execution infrastructure failures."""

    PASSED = "passed"
    TEST_FAILED = "test_failed"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


@dataclass
class TestResult:
    """Represent a test execution and its captured process output.

    Attributes:
        success: Whether pytest completed with all tests passing.
        exit_code: Process exit code, or -1 when unavailable.
        stdout: Captured standard output.
        stderr: Captured standard error.
        status: Explicit outcome classification. Existing callers can omit it.
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    status: TestStatus | None = None

    def __post_init__(self) -> None:
        """Provide backward-compatible status for manually created results."""
        if self.status is None:
            self.status = TestStatus.PASSED if self.success else TestStatus.TEST_FAILED