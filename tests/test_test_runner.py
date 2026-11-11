from unittest.mock import Mock

from multi_agent_software_team.runner.client import TestRunner as RunnerProtocol
from multi_agent_software_team.runner.models import TestResult as RunnerResult

def test_result_stores_successful_execution():
    """Verify that TestResult represents a successful test execution.

    A successful execution must preserve:
    - Whether the test process succeeded.
    - The process exit code.
    - The standard output.
    - The standard error.
    """
    result = RunnerResult(
        success=True,
        exit_code=0,
        stdout="7 passed in 0.05s",
        stderr="",
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "7 passed in 0.05s"
    assert result.stderr == ""


def test_result_stores_failed_execution():
    """Verify that TestResult represents a failed test execution.

    Failed executions must preserve diagnostic information so
    the orchestrator can inspect the failure and eventually
    provide feedback to the developer agent.
    """
    result = RunnerResult(
        success=False,
        exit_code=1,
        stdout="1 failed, 6 passed",
        stderr="AssertionError",
    )

    assert result.success is False
    assert result.exit_code == 1
    assert result.stdout == "1 failed, 6 passed"
    assert result.stderr == "AssertionError"

def test_runner_interface_returns_test_result():
    """Verify that test runners follow a common execution contract.

    The runner receives generated Python code and pytest tests,
    then returns a TestResult containing the execution outcome.

    A mock is used because no real execution backend exists yet.
    """
    runner = Mock(spec=RunnerProtocol)

    expected_result = RunnerResult(
        success=True,
        exit_code=0,
        stdout="3 passed",
        stderr="",
    )

    runner.run.return_value = expected_result

    result = runner.run(
        code="def add(a, b): return a + b",
        tests="def test_add(): assert True",
    )

    runner.run.assert_called_once_with(
        code="def add(a, b): return a + b",
        tests="def test_add(): assert True",
    )

    assert result is expected_result