"""Tests for the complete CLI-to-orchestrator wiring."""

from unittest.mock import Mock

import pytest

from multi_agent_software_team import cli
from multi_agent_software_team.runner.models import TestResult as RunnerResult, TestStatus as RunnerStatus


class FakeLLM:
    """Return predictable answers for all three agents and one revision."""

    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if "QA engineer" in prompt:
            return "from solution import add\ndef test_add(): assert add(2, 3) == 5"
        if "software developer" in prompt:
            return "def add(a, b): return a + b" if len([p for p in self.prompts if "software developer" in p]) > 1 else "def add(a, b): return a - b"
        return "- Add two integers"


@pytest.fixture
def cli_deps(monkeypatch):
    llm = FakeLLM()
    runner = Mock()
    monkeypatch.setattr(cli, "GeminiClient", lambda: llm)
    monkeypatch.setattr(cli, "DockerTestRunner", lambda image: runner)
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    return llm, runner


def test_cli_generates_without_executing_code(cli_deps, capsys):
    llm, runner = cli_deps
    assert cli.main(["Implement addition", "--generate-only"]) == 0
    assert len(llm.prompts) == 3
    runner.run.assert_not_called()
    assert "not executed" in capsys.readouterr().out


def test_cli_runs_end_to_end_with_retry_and_history(cli_deps, monkeypatch, capsys):
    llm, runner = cli_deps
    runner.run.side_effect = [
        RunnerResult(False, 1, "assert -1 == 5", "", RunnerStatus.TEST_FAILED),
        RunnerResult(True, 0, "1 passed", "", RunnerStatus.PASSED),
    ]
    assert cli.main(["Implement addition"]) == 0
    assert runner.run.call_count == 2
    assert len(llm.prompts) == 4
    output = capsys.readouterr().out
    assert "attempt 1" in output.lower()
    assert "attempt 2" in output.lower()
    assert "COMPLETED" in output


def test_cli_allows_noninteractive_docker_execution(cli_deps, monkeypatch):
    _, runner = cli_deps
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    runner.run.return_value = RunnerResult(True, 0, "1 passed", "", RunnerStatus.PASSED)
    assert cli.main(["Implement addition"]) == 0
    runner.run.assert_called_once()


def test_cli_rejects_invalid_attempts(cli_deps):
    with pytest.raises(SystemExit) as error:
        cli.main(["--example", "--max-attempts", "0"])
    assert error.value.code == 2


def test_cli_reports_failed_mission(cli_deps, monkeypatch):
    _, runner = cli_deps
    runner.run.return_value = RunnerResult(False, 1, "failure", "", RunnerStatus.TEST_FAILED)
    assert cli.main(["Implement addition", "--run-tests", "--max-attempts", "1"]) == 1


def test_package_entrypoint_delegates(monkeypatch):
    import multi_agent_software_team
    monkeypatch.setattr(cli, "main", lambda: 17)
    assert multi_agent_software_team.main() == 17
