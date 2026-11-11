"""Regression tests for readable pytest errors and code change presentation."""

from io import StringIO

from rich.console import Console

from multi_agent_software_team.models import ExecutionAttempt, Mission, MissionStatus
from multi_agent_software_team.presentation import RichPresenter
from multi_agent_software_team.runner.models import TestStatus as RunnerStatus


def presenter_output(mission: Mission, *, verbose: bool = False) -> str:
    output = StringIO()
    presenter = RichPresenter(Console(file=output, force_terminal=False, width=100), verbose=verbose)
    presenter.show_result(mission, tests_enabled=True)
    return output.getvalue()


def mission_with_retry() -> Mission:
    mission = Mission(description="Add two numbers")
    mission.status = MissionStatus.COMPLETED
    mission.code = "def add(a, b):\n    if not isinstance(a, int):\n        raise TypeError()\n    return a + b\n"
    mission.requirements = ["Add two integers"]
    mission.tests = "from solution import add\ndef test_add(): assert add(2, 3) == 5"
    mission.attempts = 2
    mission.history = [
        ExecutionAttempt(1, "def add(a, b):\n    return a + b\n", RunnerStatus.TEST_FAILED, 1, "1 failed", ""),
        ExecutionAttempt(2, mission.code, RunnerStatus.PASSED, 0, "1 passed", ""),
    ]
    return mission


def test_failure_summary_shows_actual_error_not_truncated():
    output = """_________________ test_add_invalid_types __________________
>       with pytest.raises(TypeError):
E       Failed: DID NOT RAISE <class 'TypeError'>
FAILED test_solution.py::test_add_invalid_types - Failed: DID NOT RAISE <class 'TypeError'>
"""
    summary = RichPresenter._failure_summary(output)
    assert "test_add_invalid_types" in summary
    assert "DID NOT RAISE <class 'TypeError'>" in summary
    assert "..." not in summary


def test_failure_summary_supports_short_pytest_output():
    summary = RichPresenter._failure_summary("FAILED test_solution.py::test_add - AssertionError: expected 5")
    assert "test_add" in summary
    assert "AssertionError: expected 5" in summary


def test_diff_contains_added_and_removed_lines():
    diff = RichPresenter._code_diff("return a - b\n", "return a + b\n")
    assert "-return a - b" in diff
    assert "+return a + b" in diff


def test_default_presentation_summarizes_changes():
    output = presenter_output(mission_with_retry())
    assert "Developer corrections" in output
    assert "added, " in output
    assert "use --verbose for diff" in output
    assert "previous_attempt.py" not in output


def test_verbose_presentation_shows_full_diff_and_pytest():
    output = presenter_output(mission_with_retry(), verbose=True)
    assert "previous_attempt.py" in output
    assert "corrected_attempt.py" in output
    assert "raise TypeError()" in output
    assert "Pytest output: attempt 1" in output


def test_single_attempt_does_not_show_diff():
    mission = mission_with_retry()
    mission.history = mission.history[:1]
    mission.attempts = 1
    output = presenter_output(mission, verbose=True)
    assert "Developer corrections" not in output
