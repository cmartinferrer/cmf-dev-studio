import pytest

from multi_agent_software_team.runner.docker import DockerTestRunner as DockerRunner
from multi_agent_software_team.runner.models import TestStatus as RunnerStatus

@pytest.mark.integration
def test_docker_runner_executes_valid_python_code():
    """Verify that Docker executes valid Python code and passing tests.

    This integration test uses trusted, predefined Python source code.
    It requires a running Docker daemon and the dedicated runner image.
    """
    runner = DockerRunner()

    result = runner.run(
        code="def add(a, b):\n    return a + b\n",
        tests=(
            "from solution import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    )

    assert result.success is True, result.stderr
    assert result.status == RunnerStatus.PASSED
    assert result.exit_code == 0
    assert "1 passed" in result.stdout


@pytest.mark.integration
def test_docker_runner_reports_failing_python_tests():
    """Verify that Docker reports assertion failures correctly.

    Failing pytest assertions must be classified as test failures,
    not as Docker infrastructure errors.
    """
    runner = DockerRunner()

    result = runner.run(
        code="def add(a, b):\n    return a - b\n",
        tests=(
            "from solution import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    )

    assert result.success is False
    assert result.status == RunnerStatus.TEST_FAILED
    assert result.exit_code == 1
    assert "FAILED" in result.stdout