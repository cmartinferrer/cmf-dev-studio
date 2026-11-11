
from unittest.mock import Mock

import pytest

from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.runner.models import (
    TestResult as RunnerResult,
    TestStatus as RunnerStatus,
)


@pytest.fixture
def mission():
    """Create a fresh mission for each test."""
    return Mission(description="Implement an addition function")


@pytest.fixture
def orchestrator_factory():
    """Create an orchestrator with deterministic agent behavior."""

    def create(runner=None):
        llm = Mock()
        orchestrator = Orchestrator(llm=llm, runner=runner)

        def analyst_execute(mission):
            mission.requirements = ["Add two integers"]

        def developer_execute(mission):
            mission.code = "def add(a, b): return a + b"

        def tester_execute(mission):
            mission.tests = (
                "from solution import add\n"
                "def test_add(): assert add(2, 3) == 5"
            )

        orchestrator.analyst.execute = Mock(
            side_effect=analyst_execute
        )
        orchestrator.developer.execute = Mock(
            side_effect=developer_execute
        )
        orchestrator.tester.execute = Mock(
            side_effect=tester_execute
        )

        return orchestrator

    return create


def make_result(
    status: RunnerStatus,
    success: bool,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
) -> RunnerResult:
    """Build a controlled test execution result."""
    return RunnerResult(
        success=success,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )


def test_orchestrator_without_runner(
    orchestrator_factory,
    mission,
):
    """Preserve the existing workflow without a test runner."""
    orchestrator = orchestrator_factory()

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.COMPLETED
    assert result.attempts == 0
    assert result.feedback == ""
    assert result.code
    assert result.tests


def test_orchestrator_completes_when_tests_pass(
    orchestrator_factory,
    mission,
):
    """Complete the mission when the runner reports passing tests."""
    runner = Mock()
    runner.run.return_value = make_result(
        status=RunnerStatus.PASSED,
        success=True,
        exit_code=0,
        stdout="1 passed",
    )

    orchestrator = orchestrator_factory(runner=runner)

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.COMPLETED
    assert result.attempts == 1
    assert result.feedback == "1 passed"

    runner.run.assert_called_once_with(
        code=mission.code,
        tests=mission.tests,
    )


def test_orchestrator_fails_when_tests_fail(
    orchestrator_factory,
    mission,
):
    """Fail the mission when pytest reports failing assertions."""
    runner = Mock()
    runner.run.return_value = make_result(
        status=RunnerStatus.TEST_FAILED,
        success=False,
        exit_code=1,
        stdout="AssertionError: expected 5",
    )

    orchestrator = orchestrator_factory(runner=runner)

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.FAILED
    assert result.attempts == 3
    assert runner.run.call_count == 3
    assert "test_failed" in result.feedback
    assert "AssertionError" in result.feedback


def test_orchestrator_fails_on_infrastructure_error(
    orchestrator_factory,
    mission,
):
    """Fail the mission when Docker infrastructure is unavailable."""
    runner = Mock()
    runner.run.return_value = make_result(
        status=RunnerStatus.INFRASTRUCTURE_ERROR,
        success=False,
        exit_code=-1,
        stderr="Cannot connect to the Docker daemon",
    )

    orchestrator = orchestrator_factory(runner=runner)

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.FAILED
    assert result.attempts == 1
    assert "infrastructure_error" in result.feedback
    assert "Cannot connect" in result.feedback


def test_orchestrator_handles_runner_exception(
    orchestrator_factory,
    mission,
):
    """Handle unexpected runner exceptions without crashing."""
    runner = Mock()
    runner.run.side_effect = RuntimeError("Runner unavailable")

    orchestrator = orchestrator_factory(runner=runner)

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.FAILED
    assert result.attempts == 1
    assert result.feedback == "Runner unavailable"


def test_orchestrator_does_not_run_tests_when_agent_fails(
    orchestrator_factory,
    mission,
):
    """Skip test execution if an earlier agent fails."""
    runner = Mock()
    orchestrator = orchestrator_factory(runner=runner)

    orchestrator.developer.execute.side_effect = RuntimeError(
        "Developer failed"
    )

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.FAILED
    assert result.feedback == "Developer failed"
    assert result.attempts == 0
    runner.run.assert_not_called()


def test_orchestrator_rejects_inconsistent_success_result(
    orchestrator_factory,
    mission,
):
    """Do not complete a mission with an inconsistent runner result."""
    runner = Mock()
    runner.run.return_value = make_result(
        status=RunnerStatus.PASSED,
        success=False,
        exit_code=0,
    )

    orchestrator = orchestrator_factory(runner=runner)

    result = orchestrator.run(mission)

    assert result.status is MissionStatus.FAILED
    assert result.attempts == 1
