"""Tests for immutable snapshots of runner execution attempts."""

from unittest.mock import Mock

import pytest

from multi_agent_software_team.models import ExecutionAttempt, Mission, MissionStatus
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.runner.models import (
    TestResult as RunnerResult,
    TestStatus as RunnerStatus,
)


def outcome(status, stdout="", stderr=""):
    """Return a deterministic runner outcome."""
    return RunnerResult(
        success=status is RunnerStatus.PASSED,
        status=status,
        exit_code=0 if status is RunnerStatus.PASSED else 1,
        stdout=stdout,
        stderr=stderr,
    )


def workflow(outcomes, max_attempts=3):
    """Build a workflow whose developer produces distinct revisions."""
    runner = Mock()
    runner.run.side_effect = outcomes
    orchestrator = Orchestrator(Mock(), runner=runner, max_attempts=max_attempts)
    orchestrator.analyst.execute = Mock(
        side_effect=lambda mission: mission.requirements.append("Add integers")
    )

    def develop(mission):
        mission.code = f"revision_{orchestrator.developer.execute.call_count}"

    orchestrator.developer.execute = Mock(side_effect=develop)
    orchestrator.tester.execute = Mock(
        side_effect=lambda mission: setattr(mission, "tests", "fixed tests")
    )
    return orchestrator, runner, Mission(description="Add integers")


def test_history_records_successful_execution():
    """Record successful test output and exact submitted code."""
    orchestrator, runner, mission = workflow([
        outcome(RunnerStatus.PASSED, stdout="1 passed")
    ])
    orchestrator.run(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert mission.attempts == len(mission.history) == 1
    assert mission.history[0] == ExecutionAttempt(
        number=1, code="revision_1", status=RunnerStatus.PASSED,
        exit_code=0, stdout="1 passed", stderr="",
    )
    runner.run.assert_called_once_with(code="revision_1", tests="fixed tests")


def test_history_preserves_failed_revision_after_correction():
    """Retain failed code and its feedback after the developer fixes it."""
    orchestrator, _, mission = workflow([
        outcome(RunnerStatus.TEST_FAILED, stderr="assertion failed"),
        outcome(RunnerStatus.PASSED, stdout="1 passed"),
    ])
    orchestrator.run(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert mission.attempts == 2
    assert [attempt.number for attempt in mission.history] == [1, 2]
    assert [attempt.code for attempt in mission.history] == ["revision_1", "revision_2"]
    assert [attempt.status for attempt in mission.history] == [
        RunnerStatus.TEST_FAILED, RunnerStatus.PASSED
    ]
    assert mission.history[0].stderr == "assertion failed"
    assert mission.history[1].stdout == "1 passed"
    assert mission.code == "revision_2"


def test_history_records_all_exhausted_attempts():
    """Retain every failed execution when retries are exhausted."""
    orchestrator, _, mission = workflow([
        outcome(RunnerStatus.TEST_FAILED, stderr=f"failure {i}") for i in range(3)
    ])
    orchestrator.run(mission)
    assert mission.status is MissionStatus.FAILED
    assert mission.attempts == len(mission.history) == 3
    assert [item.stderr for item in mission.history] == [
        "failure 0", "failure 1", "failure 2"
    ]


def test_infrastructure_error_records_one_attempt_without_retry():
    """Preserve Docker errors without triggering another development cycle."""
    orchestrator, runner, mission = workflow([
        outcome(RunnerStatus.INFRASTRUCTURE_ERROR, stderr="daemon unavailable")
    ])
    orchestrator.run(mission)
    assert mission.status is MissionStatus.FAILED
    assert mission.attempts == len(mission.history) == 1
    assert mission.history[0].status is RunnerStatus.INFRASTRUCTURE_ERROR
    assert mission.history[0].stderr == "daemon unavailable"
    runner.run.assert_called_once()


def test_no_runner_leaves_history_empty():
    """Avoid fabricating executions when validation is disabled."""
    orchestrator = Orchestrator(Mock())
    orchestrator.analyst.execute = Mock()
    orchestrator.developer.execute = Mock()
    orchestrator.tester.execute = Mock()
    mission = Mission(description="example")
    orchestrator.run(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert mission.attempts == 0
    assert mission.history == []


def test_agent_failure_before_runner_leaves_history_empty():
    """Do not record an attempt when no runner invocation occurred."""
    orchestrator, runner, mission = workflow([])
    orchestrator.developer.execute.side_effect = RuntimeError("developer unavailable")
    orchestrator.run(mission)
    assert mission.status is MissionStatus.FAILED
    assert mission.attempts == 0
    assert mission.history == []
    runner.run.assert_not_called()


def test_failure_during_revision_preserves_previous_attempt():
    """Keep earlier snapshots when the developer crashes during a retry."""
    orchestrator, runner, mission = workflow([
        outcome(RunnerStatus.TEST_FAILED, stderr="bad assertion")
    ])

    def develop(mission):
        if orchestrator.developer.execute.call_count == 2:
            raise RuntimeError("revision failed")
        mission.code = "initial"

    orchestrator.developer.execute.side_effect = develop
    orchestrator.run(mission)
    assert mission.status is MissionStatus.FAILED
    assert mission.attempts == len(mission.history) == 1
    assert mission.history[0].code == "initial"
    assert mission.history[0].stderr == "bad assertion"
    assert mission.feedback == "revision failed"
    runner.run.assert_called_once()


def test_runner_exception_does_not_create_fabricated_result():
    """Count an invoked runner even if it raises before returning a result."""
    orchestrator, runner, mission = workflow([RuntimeError("runner crashed")])
    orchestrator.run(mission)
    assert mission.status is MissionStatus.FAILED
    assert mission.attempts == 1
    assert mission.history == []
    assert mission.feedback == "runner crashed"
    runner.run.assert_called_once()


def test_history_is_reset_when_reusing_a_mission():
    """Keep history scoped to one orchestrator run, like attempts and feedback."""
    orchestrator, runner, mission = workflow([
        outcome(RunnerStatus.PASSED, stdout="first"),
        outcome(RunnerStatus.PASSED, stdout="second"),
    ])
    orchestrator.run(mission)
    assert mission.history[0].stdout == "first"
    orchestrator.run(mission)
    assert mission.attempts == len(mission.history) == 1
    assert mission.history[0].number == 1
    assert mission.history[0].stdout == "second"


def test_missions_have_independent_histories():
    """Avoid sharing the default history list across missions."""
    first = Mission(description="first")
    second = Mission(description="second")
    first.history.append(ExecutionAttempt(
        number=1, code="pass", status=RunnerStatus.PASSED,
        exit_code=0, stdout="ok", stderr="",
    ))
    assert second.history == []


def test_attempt_snapshot_is_immutable():
    """Prevent accidental changes to recorded execution evidence."""
    from dataclasses import FrozenInstanceError
    attempt = ExecutionAttempt(
        number=1, code="pass", status=RunnerStatus.PASSED,
        exit_code=0, stdout="ok", stderr="",
    )
    with pytest.raises(FrozenInstanceError):
        attempt.code = "changed"