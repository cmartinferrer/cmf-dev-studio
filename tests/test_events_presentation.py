"""Test presentation-neutral mission events and Rich terminal rendering."""

from io import StringIO
from unittest.mock import Mock

from rich.console import Console

from multi_agent_software_team.events import EventType
from multi_agent_software_team.models import Mission
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.presentation import RichPresenter
from multi_agent_software_team.runner.models import TestResult as RunnerResult, TestStatus as RunnerStatus


class FakeLLM:
    def generate(self, prompt):
        if "QA engineer" in prompt:
            return "from solution import add\ndef test_add(): assert add(2, 3) == 5"
        if "software developer" in prompt:
            return "def add(a, b): return a + b"
        return "- Add two integers"


def test_events_cover_complete_retry_lifecycle():
    events = []
    runner = Mock()
    runner.run.side_effect = [
        RunnerResult(False, 1, "FAILED test_solution.py::test_add - AssertionError", "", RunnerStatus.TEST_FAILED),
        RunnerResult(True, 0, "1 passed", "", RunnerStatus.PASSED),
    ]
    mission = Orchestrator(FakeLLM(), runner=runner, on_event=events.append).run(Mission("addition"))
    assert mission.attempts == 2
    assert [e.type for e in events] == [
        EventType.MISSION_STARTED,
        EventType.AGENT_STARTED, EventType.AGENT_COMPLETED,
        EventType.AGENT_STARTED, EventType.AGENT_COMPLETED,
        EventType.AGENT_STARTED, EventType.AGENT_COMPLETED,
        EventType.TEST_STARTED, EventType.TEST_COMPLETED,
        EventType.RETRY_STARTED, EventType.AGENT_STARTED, EventType.AGENT_COMPLETED,
        EventType.TEST_STARTED, EventType.TEST_COMPLETED,
        EventType.MISSION_COMPLETED,
    ]
    assert events[8].status == "test_failed"
    assert events[13].status == "passed"


def test_rich_presenter_explains_failed_tests_and_retries():
    output = StringIO()
    presenter = RichPresenter(Console(file=output, force_terminal=False, width=110))
    from multi_agent_software_team.events import ExecutionEvent
    presenter(ExecutionEvent(EventType.TEST_COMPLETED, attempt=1, status="test_failed", message="FAILED test_solution.py::test_add - AssertionError"))
    presenter(ExecutionEvent(EventType.RETRY_STARTED, attempt=2, max_attempts=3))
    assert "Why did it fail?" in output.getvalue()
    assert "Retrying" in output.getvalue()
