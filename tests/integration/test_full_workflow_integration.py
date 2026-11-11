"""Exercise the complete agent workflow with Docker and a deterministic LLM."""

import shutil

import pytest

from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.runner.docker import DockerTestRunner


class DeterministicLLM:
    """Generate a deliberately incorrect implementation, then repair it."""

    def generate(self, prompt: str) -> str:
        if "software requirements analyst" in prompt:
            return "Return the arithmetic sum of two integers."
        if "Python QA engineer" in prompt:
            return "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        if "previous implementation failed" in prompt:
            return "def add(a, b):\n    return a + b\n"
        return "def add(a, b):\n    return a - b\n"


@pytest.mark.integration
def test_complete_agents_retry_and_real_docker():
    """Validate Analyst -> Developer -> Tester -> Docker -> Developer -> Docker."""
    if shutil.which("docker") is None:
        pytest.skip("Docker is not installed")

    mission = Orchestrator(
        llm=DeterministicLLM(),
        runner=DockerTestRunner(),
        max_attempts=3,
    ).run(Mission(description="Implement add(a, b)"))

    assert mission.status is MissionStatus.COMPLETED, mission.feedback
    assert mission.attempts == 2
    assert [attempt.status.value for attempt in mission.history] == ["test_failed", "passed"]
    assert "return a + b" in mission.code
