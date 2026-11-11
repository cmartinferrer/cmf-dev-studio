from typing import Protocol

from multi_agent_software_team.runner.models import TestResult


class TestRunner(Protocol):
    """Define the common interface for isolated test execution.

    Implementations are responsible for executing generated
    Python code and pytest tests in a controlled environment.

    The protocol allows the orchestrator to remain independent
    of the underlying execution technology.
    """

    def run(self, code: str, tests: str) -> TestResult:
        """Execute generated tests against the provided implementation.

        Args:
            code: Python source code produced by the developer.
            tests: Pytest source code produced by the tester.

        Returns:
            A TestResult describing the execution outcome.
        """
        ...