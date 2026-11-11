"""Unit tests for the developer feedback loop and retry policy."""

from unittest.mock import Mock

import pytest

from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.runner.models import (
    TestResult as RunnerResult,
    TestStatus as RunnerStatus,
)


def result(status, stdout="", stderr=""):
    """Create a controlled runner result."""
    return RunnerResult(
        success=status is RunnerStatus.PASSED,
        exit_code=0 if status is RunnerStatus.PASSED else 1,
        stdout=stdout,
        stderr=stderr,
        status=status,
    )


@pytest.fixture
def setup_workflow():
    """Provide mocked agents that preserve their shared mission state."""
    def create(outcomes, max_attempts=3):
        runner = Mock()
        runner.run.side_effect = outcomes
        orchestrator = Orchestrator(Mock(), runner=runner, max_attempts=max_attempts)
        orchestrator.analyst.execute = Mock(
            side_effect=lambda mission: mission.requirements.append("Add integers")
        )

        def develop(mission):
            mission.code = f"implementation_{orchestrator.developer.execute.call_count}"

        orchestrator.developer.execute = Mock(side_effect=develop)
        orchestrator.tester.execute = Mock(
            side_effect=lambda mission: setattr(mission, "tests", "fixed tests")
        )
        return orchestrator, runner, Mission(description="Add two integers")
    return create


def test_retries_until_tests_pass(setup_workflow):
    """Retry a failed implementation and finish after a passing result."""
    orchestrator, runner, mission = setup_workflow([
        result(RunnerStatus.TEST_FAILED, stderr="AssertionError"),
        result(RunnerStatus.PASSED, stdout="1 passed"),
    ])
    output = orchestrator.run(mission)
    assert output.status is MissionStatus.COMPLETED
    assert output.attempts == 2
    assert output.feedback == "1 passed"
    assert orchestrator.analyst.execute.call_count == 1
    assert orchestrator.tester.execute.call_count == 1
    assert orchestrator.developer.execute.call_count == 2
    assert runner.run.call_count == 2
    assert runner.run.call_args.kwargs["code"] == "implementation_2"


def test_stops_after_max_attempts(setup_workflow):
    """Stop retrying when all permitted attempts have failed."""
    orchestrator, runner, mission = setup_workflow([
        result(RunnerStatus.TEST_FAILED, stderr="failed") for _ in range(3)
    ])
    output = orchestrator.run(mission)
    assert output.status is MissionStatus.FAILED
    assert output.attempts == 3
    assert orchestrator.developer.execute.call_count == 3
    assert runner.run.call_count == 3


def test_infrastructure_error_is_not_retried(setup_workflow):
    """Do not ask the developer to fix a Docker infrastructure problem."""
    orchestrator, runner, mission = setup_workflow([
        result(RunnerStatus.INFRASTRUCTURE_ERROR, stderr="Docker unavailable")
    ])
    output = orchestrator.run(mission)
    assert output.status is MissionStatus.FAILED
    assert output.attempts == 1
    assert "Docker unavailable" in output.feedback
    assert orchestrator.developer.execute.call_count == 1
    runner.run.assert_called_once()


def test_first_attempt_passes_without_retry(setup_workflow):
    """Avoid additional development when the initial tests pass."""
    orchestrator, runner, mission = setup_workflow([
        result(RunnerStatus.PASSED, stdout="passed")
    ])
    assert orchestrator.run(mission).status is MissionStatus.COMPLETED
    assert mission.attempts == 1
    assert orchestrator.developer.execute.call_count == 1
    runner.run.assert_called_once()


def test_max_attempts_one_disables_retries(setup_workflow):
    """A single attempt must never trigger a correction."""
    orchestrator, _, mission = setup_workflow([
        result(RunnerStatus.TEST_FAILED, stderr="failed")
    ], max_attempts=1)
    assert orchestrator.run(mission).status is MissionStatus.FAILED
    assert mission.attempts == 1
    assert orchestrator.developer.execute.call_count == 1


def test_rejects_invalid_max_attempts():
    """Reject nonpositive retry limits."""
    with pytest.raises(ValueError, match="max_attempts"):
        Orchestrator(Mock(), max_attempts=0)


def test_without_runner_preserves_old_behavior():
    """The default orchestrator must not execute generated code."""
    orchestrator = Orchestrator(Mock())
    orchestrator.analyst.execute = Mock()
    orchestrator.developer.execute = Mock()
    orchestrator.tester.execute = Mock()
    mission = Mission(description="example")
    assert orchestrator.run(mission).status is MissionStatus.COMPLETED
    assert mission.attempts == 0


def test_developer_includes_previous_code_and_feedback():
    """Give the LLM enough context to repair a failing implementation."""
    llm = Mock()
    llm.generate.return_value = "def add(a, b): return a + b"
    mission = Mission(
        description="Add integers",
        requirements=["Return the sum"],
        code="def add(a, b): return a - b\n",
        feedback="AssertionError: expected 5",
    )
    DeveloperAgent(llm).execute(mission)
    prompt = llm.generate.call_args.args[0]
    assert "return a - b" in prompt
    assert "AssertionError: expected 5" in prompt
    assert "Return the sum" in prompt
    assert mission.code == "def add(a, b): return a + b\n"


def test_developer_initial_prompt_has_no_revision_context():
    """Keep initial code generation independent from test feedback."""
    llm = Mock()
    llm.generate.return_value = "pass"
    DeveloperAgent(llm).execute(Mission(description="example"))
    assert "Previous implementation:" not in llm.generate.call_args.args[0]