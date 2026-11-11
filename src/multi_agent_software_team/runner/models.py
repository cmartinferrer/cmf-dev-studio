from dataclasses import dataclass


@dataclass
class TestResult:
    """Represent the outcome of an isolated test execution.

    Attributes:
        success: Whether the test process completed successfully.
        exit_code: Exit status returned by the test process.
        stdout: Standard output captured during execution.
        stderr: Standard error captured during execution.
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str