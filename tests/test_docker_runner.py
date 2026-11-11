import subprocess

from unittest.mock import patch

from multi_agent_software_team.runner.docker import DockerTestRunner as DockerRunner
from multi_agent_software_team.runner.models import TestStatus as RunnerStatus

def test_docker_runner_builds_secure_command():
    """Verify that Docker execution uses restrictive security options.

    Generated code must run without network access, additional
    privileges, or unrestricted access to system resources.

    This test only inspects the Docker command. It does not
    execute any container.
    """
    runner = DockerRunner()

    command = runner.build_command("/tmp/generated-tests")

    assert command[0:3] == ["docker", "run", "--rm"]

    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command

    assert "--memory=256m" in command
    assert "--cpus=1" in command

    assert "--pids-limit=64" in command

def test_docker_runner_uses_custom_image():
    """Verify that the runner uses the configured Docker image.

    A dedicated image ensures that pytest and its dependencies
    are available without installing packages during execution.
    """
    runner = DockerRunner(image="custom-test-runner:1.0")

    command = runner.build_command("/tmp/generated-tests")

    assert "custom-test-runner:1.0" in command
    assert "python:3.12-slim" not in command


def test_docker_runner_prepares_generated_files(tmp_path):
    """Verify that generated code and tests are written to separate files.

    The runner must prepare a solution module and a pytest module
    inside the execution workspace.

    This test does not start Docker or execute generated code.
    """
    runner = DockerRunner()

    code = "def add(a, b):\n    return a + b\n"
    tests = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    runner.prepare_workspace(
        workspace=tmp_path,
        code=code,
        tests=tests,
    )

    solution_file = tmp_path / "solution.py"
    test_file = tmp_path / "test_solution.py"

    assert solution_file.is_file()
    assert test_file.is_file()

    assert solution_file.read_text(encoding="utf-8") == code
    assert test_file.read_text(encoding="utf-8") == tests

def test_docker_runner_executes_tests_successfully():
    """Verify that the runner returns a successful test execution result.

    The runner must prepare a temporary workspace, invoke Docker
    with the generated files, and convert the process output
    into a TestResult.

    Docker execution is mocked to avoid running generated code.
    """
    runner = DockerRunner()

    code = "def add(a, b): return a + b"
    tests = "def test_add(): assert True"

    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed in 0.02s"
        mock_run.return_value.stderr = ""

        result = runner.run(code=code, tests=tests)

    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "1 passed in 0.02s"
    assert result.stderr == ""

    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args

    assert kwargs["timeout"] == 30
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False


def test_docker_runner_returns_failed_test_result():
    """Verify that failing pytest tests produce an unsuccessful result.

    A non-zero pytest exit code must be preserved together with
    its output so that the orchestrator can identify the failure
    and provide useful feedback to the developer agent.

    Docker execution is mocked to avoid running generated code.
    """
    runner = DockerRunner()

    code = "def add(a, b): return a - b"
    tests = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = (
            "FAILED test_solution.py::test_add\n"
            "AssertionError: assert -1 == 5"
        )
        mock_run.return_value.stderr = ""

        result = runner.run(code=code, tests=tests)

    assert result.success is False
    assert result.exit_code == 1
    assert "FAILED test_solution.py::test_add" in result.stdout
    assert "AssertionError" in result.stdout
    assert result.stderr == ""

    mock_run.assert_called_once()

def test_docker_runner_handles_missing_docker():
    """Verify that the runner handles an unavailable Docker executable.

    When Docker cannot be started, the runner must return an
    unsuccessful TestResult instead of propagating FileNotFoundError.

    The error message must explain the infrastructure problem
    so it can be distinguished from a failing pytest assertion.
    """
    runner = DockerRunner()

    with (
        patch(
            "multi_agent_software_team.runner.docker.subprocess.run",
            side_effect=FileNotFoundError("docker executable not found"),
        ),
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        result = runner.run(
            code="def add(a, b): return a + b",
            tests="def test_add(): assert True",
        )

    assert result.success is False
    assert result.exit_code == -1
    assert result.stdout == ""
    assert "Docker execution failed" in result.stderr
    assert "docker executable not found" in result.stderr

def test_docker_runner_handles_execution_timeout():
    """Verify that execution timeouts produce an unsuccessful result.

    The runner must handle subprocess.TimeoutExpired without
    propagating the exception to the orchestrator.

    Timeout errors must be identifiable as infrastructure
    failures rather than failed pytest assertions.

    Docker execution is mocked to avoid starting a container.
    """
    runner = DockerRunner()

    with (
        patch(
            "multi_agent_software_team.runner.docker.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=["docker", "run"],
                timeout=30,
            ),
        ),
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        result = runner.run(
            code="while True: pass",
            tests="def test_example(): assert True",
        )

    assert result.success is False
    assert result.exit_code == -1
    assert result.stdout == ""
    assert "timed out" in result.stderr.lower()
    assert "30" in result.stderr

def test_docker_runner_assigns_container_name():
    """Verify that Docker containers receive an explicit name.

    A predictable container name allows the runner to identify
    and remove a specific container if execution times out.

    This test only inspects the generated Docker command.
    """
    runner = DockerRunner()

    command = runner.build_command(
        workspace="/tmp/generated-tests",
        container_name="multi-agent-test-123",
    )

    assert "--name" in command

    name_index = command.index("--name")
    assert command[name_index + 1] == "multi-agent-test-123"

def test_docker_runner_generates_unique_container_names():
    """Verify that each execution uses a unique Docker container name.

    Container names must be unique to prevent collisions between
    concurrent or successive test executions.

    Docker execution is mocked to avoid starting containers.
    """
    runner = DockerRunner()
    container_names = []

    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed"
        mock_run.return_value.stderr = ""

        for _ in range(2):
            runner.run(
                code="def add(a, b): return a + b",
                tests="def test_add(): assert True",
            )

        for call in mock_run.call_args_list:
            command = call.args[0]

            assert "--name" in command

            name_index = command.index("--name")
            container_names.append(command[name_index + 1])

    assert len(container_names) == 2
    assert container_names[0] != container_names[1]

    assert all(
        name.startswith("multi-agent-test-")
        for name in container_names
    )

def test_docker_runner_cleans_up_container():
    """Verify that the runner can forcibly remove a Docker container.

    The cleanup operation must target only the specified container
    and must not fail if Docker reports that it no longer exists.

    Docker execution is mocked to avoid removing real containers.
    """
    runner = DockerRunner()

    with patch(
        "multi_agent_software_team.runner.docker.subprocess.run"
    ) as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = "Error: No such object: multi-agent-test-123"

        runner.cleanup_container("multi-agent-test-123")

    assert mock_run.call_count == 2
    mock_run.assert_any_call(
        ["docker", "rm", "--force", "multi-agent-test-123"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

def test_docker_runner_cleans_up_after_successful_execution():
    """Verify that container cleanup runs after a successful execution.

    The runner must clean up the exact container created for the
    execution, even when pytest completes successfully.

    Both Docker execution and cleanup are mocked.
    """
    runner = DockerRunner()

    with (
        patch(
            "multi_agent_software_team.runner.docker.subprocess.run"
        ) as mock_run,
        patch.object(runner, "cleanup_container", return_value=True) as mock_cleanup,
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed"
        mock_run.return_value.stderr = ""

        result = runner.run(
            code="def add(a, b): return a + b",
            tests="def test_add(): assert True",
        )

    assert result.success is True

    command = mock_run.call_args.args[0]
    container_name = command[command.index("--name") + 1]

    mock_cleanup.assert_called_once_with(container_name)

def test_docker_runner_detects_existing_container():
    """Verify that a successful Docker inspection confirms container presence."""
    runner = DockerRunner()
    with patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert runner.container_exists("multi-agent-test-123") is True
    mock_run.assert_called_once_with(
        ["docker", "container", "inspect", "--format", "{{.Id}}", "multi-agent-test-123"],
        capture_output=True, text=True, timeout=10, check=False,
    )


def test_docker_runner_detects_missing_container():
    """Verify that Docker's explicit not-found response confirms absence."""
    runner = DockerRunner()
    with patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error: No such object: multi-agent-test-123"
        assert runner.container_exists("multi-agent-test-123") is False


def test_docker_runner_reports_container_inspection_failure():
    """Verify that an unavailable Docker executable yields an unknown state."""
    runner = DockerRunner()
    with patch(
        "multi_agent_software_team.runner.docker.subprocess.run",
        side_effect=FileNotFoundError("Docker unavailable"),
    ):
        assert runner.container_exists("multi-agent-test-123") is None


def test_docker_runner_does_not_confuse_inspection_error_with_absence():
    """Verify that daemon errors are not treated as missing containers."""
    runner = DockerRunner()
    with patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Cannot connect to the Docker daemon"
        assert runner.container_exists("multi-agent-test-123") is None


def test_docker_runner_confirms_container_removal():
    """Verify that cleanup succeeds when inspection confirms absence.

    A non-zero removal status can be harmless when --rm already removed
    the container, so confirmation must come from inspection.
    """
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "container_exists", return_value=False) as mock_exists,
    ):
        mock_run.return_value.returncode = 1
        assert runner.cleanup_container("multi-agent-test-123") is True
    mock_exists.assert_called_once_with("multi-agent-test-123")


def test_docker_runner_detects_cleanup_failure():
    """Verify that a still-existing container causes cleanup to fail."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "container_exists", return_value=True) as mock_exists,
    ):
        mock_run.return_value.returncode = 1
        assert runner.cleanup_container("multi-agent-test-123") is False
    mock_exists.assert_called_once_with("multi-agent-test-123")


def test_docker_runner_reports_successful_cleanup():
    """Verify that confirmed container absence yields successful cleanup."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "container_exists", return_value=False) as mock_exists,
    ):
        mock_run.return_value.returncode = 0
        assert runner.cleanup_container("multi-agent-test-123") is True
    mock_exists.assert_called_once_with("multi-agent-test-123")


def test_docker_runner_cleans_up_after_timeout():
    """Verify that a timeout triggers cleanup for the same container."""
    runner = DockerRunner()
    with (
        patch(
            "multi_agent_software_team.runner.docker.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=30),
        ) as mock_run,
        patch.object(runner, "cleanup_container", return_value=True) as mock_cleanup,
    ):
        result = runner.run("while True: pass", "def test_example(): assert True")
    assert result.success is False
    assert "timed out" in result.stderr.lower()
    command = mock_run.call_args.args[0]
    mock_cleanup.assert_called_once_with(command[command.index("--name") + 1])


def test_docker_runner_rejects_unconfirmed_cleanup():
    """Verify that unconfirmed cleanup prevents a successful result."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=False),
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed"
        mock_run.return_value.stderr = ""
        result = runner.run("def add(a, b): return a + b", "def test_add(): assert True")
    assert result.success is False
    assert result.exit_code == -1
    assert result.stdout == "1 passed"
    assert "cleanup could not be confirmed" in result.stderr


def test_runner_classifies_pytest_failure():
    """Verify that a pytest assertion failure is not a Docker error."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = "FAILED test_solution.py::test_add"
        mock_run.return_value.stderr = ""
        result = runner.run("def add(): return 0", "def test_add(): assert False")
    assert result.status is RunnerStatus.TEST_FAILED
    assert result.success is False


def test_runner_classifies_docker_daemon_failure():
    """Verify that an unavailable Docker daemon is an infrastructure error."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Cannot connect to the Docker daemon"
        result = runner.run("pass", "def test_example(): assert True")
    assert result.status is RunnerStatus.INFRASTRUCTURE_ERROR
    assert result.success is False


def test_runner_classifies_docker_exit_code_125():
    """Verify that Docker CLI failures are infrastructure errors."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        mock_run.return_value.returncode = 125
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "docker: invalid reference format"
        result = runner.run("pass", "def test_example(): assert True")
    assert result.status is RunnerStatus.INFRASTRUCTURE_ERROR


def test_runner_classifies_cleanup_failure_as_infrastructure_error():
    """Verify that unconfirmed cleanup overrides an otherwise passing run."""
    runner = DockerRunner()
    with (
        patch("multi_agent_software_team.runner.docker.subprocess.run") as mock_run,
        patch.object(runner, "cleanup_container", return_value=False),
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed"
        mock_run.return_value.stderr = ""
        result = runner.run("pass", "def test_example(): assert True")
    assert result.status is RunnerStatus.INFRASTRUCTURE_ERROR
    assert result.success is False
    assert "cleanup" in result.stderr.lower()


def test_runner_classifies_timeout_as_infrastructure_error():
    """Verify that subprocess timeouts cannot be mistaken for pytest failures."""
    runner = DockerRunner()
    with (
        patch(
            "multi_agent_software_team.runner.docker.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["docker", "run"], 30),
        ),
        patch.object(runner, "cleanup_container", return_value=True),
    ):
        result = runner.run("pass", "def test_example(): assert True")
    assert result.status is RunnerStatus.INFRASTRUCTURE_ERROR